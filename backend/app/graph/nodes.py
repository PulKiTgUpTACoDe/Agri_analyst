"""LangGraph node functions – detect intent, fetch data, analyze, answer."""
import asyncio
import logging
import time
from datetime import date, datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.graph.state import AgentState
from app.core.config import get_settings
from app.core.schemas import QueryIntent, DataQuality
from app.core.api_client import get_client
from app.core.open_meteo import get_meteo_client
from app.core.geocoding import resolve_location
from app.core.data_sources import get_registry
from app.core.cache import get_cache
from app.utils.aggregation import (
    top_n_ranking, calculate_trend, aggregate_by_group,
    aggregate_multi_year_average, calculate_year_over_year_growth,
)
from app.utils.correlation import (
    correlate_production_with_climate, identify_optimal_conditions,
    compare_climate_impact,
)
from app.utils.policy_synthesis import (
    generate_policy_arguments, generate_comparative_summary,
)

logger = logging.getLogger("agri.nodes")

_llm = None

def get_llm():
    """Get shared LLM instance (avoid recreating per node)."""
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
        )
    return _llm

async def detect_intent(state: AgentState) -> AgentState:
    """Detect query intent and extract parameters using LLM."""
    start = time.monotonic()
    today = date.today()
    current_year = today.year

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an intent classifier for an Indian agriculture data system.
Today's date is {today.isoformat()}. The current year is {current_year}.

Extract the query intent and parameters. Output JSON matching the QueryIntent schema.

Query types:
- comparison: comparing entities (states/crops/districts)
- trend: analyzing changes over time
- correlation: relationships between variables (e.g., rainfall vs production)
- policy: recommendations/arguments with data backing
- ranking: top/bottom performers
- forecast: weather forecast for agricultural planning
- current_weather: current weather conditions at a location
- general: simple factual questions about agriculture

Data sources available:
1. daily_price_params: Current daily mandi prices (state, district, market, commodity, variety)
2. variety_price_params: Variety-wise prices (state, district, commodity)
3. production_params: Crop production stats from 1997 (state_name, district_name, crop, crop_year, season)
4. weather_params: Real-time & historical weather (state, district, subdivision, start_year, end_year, include_forecast, include_current)

IMPORTANT RULES:
- When user asks about "recent" or "latest" data, use current year ({current_year}) as end_year
- For weather/temperature/rainfall queries, always set weather_params with the relevant state/district
- If user asks about forecast or "tomorrow", set include_forecast=true
- If user asks about "current weather" or "today's weather", set include_current=true
- For historical weather comparisons, set start_year and end_year in weather_params

EXAMPLES:
Q: "What is the current price of wheat in Punjab?"
A: daily_price_params with state="Punjab", commodity="Wheat"

Q: "What was the rainfall in Maharashtra last year?"
A: weather_params with state="Maharashtra", start_year={current_year - 1}, end_year={current_year - 1}

Q: "Compare rice production in Punjab vs Haryana in the last 5 years"
A: production_params with crop="Rice", crop_year={current_year - 1} (for most recent), entities=["Punjab", "Haryana"], query_type="comparison"

Q: "What's the weather forecast for farming in UP?"
A: query_type="forecast", weather_params with state="Uttar Pradesh", include_forecast=true"""),
        ("human", "{question}")
    ])

    chain = prompt | get_llm().with_structured_output(QueryIntent)
    intent = await chain.ainvoke({"question": state["question"]})

    elapsed = (time.monotonic() - start) * 1000
    logger.info("Intent detected: type=%s entities=%s (%.0fms)", intent.query_type, intent.entities, elapsed)

    state["intent"] = intent
    state["timing"]["detect_intent"] = round(elapsed, 1)
    return state

async def select_sources(state: AgentState) -> AgentState:
    """Select which data sources to query based on intent."""
    start = time.monotonic()
    intent = state["intent"]
    sources = []

    if intent.daily_price_params:
        sources.append("daily_prices")
    if intent.variety_price_params:
        sources.append("variety_prices")
    if intent.production_params:
        sources.append("crop_production")

    # Weather sources
    if intent.weather_params:
        wp = intent.weather_params
        if wp.include_current:
            sources.append("weather_current")
        if wp.include_forecast:
            sources.append("weather_forecast")
        if wp.start_year or wp.end_year:
            # Historical weather → figure out if it's temperature or rainfall
            metrics = [m.lower() for m in intent.metrics]
            if any(kw in metrics for kw in ["temperature", "temp", "heat", "cold"]):
                sources.append("temperature_data")
            if any(kw in metrics for kw in ["rainfall", "rain", "precipitation", "monsoon"]):
                sources.append("rainfall_data")
            if not sources or all(s in ("weather_current", "weather_forecast") for s in sources):
                # Default to both weather types for historical
                sources.extend(["temperature_data", "rainfall_data"])

    elapsed = (time.monotonic() - start) * 1000
    logger.info("Sources selected: %s (%.0fms)", sources, elapsed)

    state["sources_selected"] = sources
    state["timing"]["select_sources"] = round(elapsed, 1)
    return state

async def fetch_data(state: AgentState) -> AgentState:
    """Fetch data from all selected sources in parallel."""
    start = time.monotonic()
    intent = state["intent"]
    sources = state.get("sources_selected", [])
    client = get_client()
    meteo = get_meteo_client()
    cache = get_cache()
    registry = get_registry()

    # Inject cache into clients
    client.set_cache(cache)
    meteo.set_cache(cache)

    tasks = {}

    # ── data.gov.in sources ───────────────────────────────────────────────
    if "daily_prices" in sources and intent.daily_price_params:
        p = intent.daily_price_params
        ds = registry.get_source("daily_prices")
        tasks["daily_prices"] = client.fetch(
            resource_id=ds.resource_id,
            filters={"state.keyword": p.state, "district": p.district,
                     "market": p.market, "commodity": p.commodity, "variety": p.variety},
        )

    if "variety_prices" in sources and intent.variety_price_params:
        p = intent.variety_price_params
        ds = registry.get_source("variety_prices")
        tasks["variety_prices"] = client.fetch(
            resource_id=ds.resource_id,
            filters={"State": p.state, "District": p.district, "Commodity": p.commodity},
        )

    if "crop_production" in sources and intent.production_params:
        p = intent.production_params
        ds = registry.get_source("crop_production")
        tasks["crop_production"] = client.fetch(
            resource_id=ds.resource_id,
            filters={"state_name": p.state_name, "district_name": p.district_name,
                     "crop": p.crop, "crop_year": p.crop_year, "season": p.season},
            limit=5000,
        )

    # ── Open-Meteo weather sources ────────────────────────────────────────
    weather_location = None
    if intent.weather_params:
        wp = intent.weather_params
        weather_location = resolve_location(
            state=wp.state, district=wp.district, subdivision=wp.subdivision
        )
        if not weather_location and intent.entities:
            # Try entities as state names
            for entity in intent.entities:
                weather_location = resolve_location(state=entity)
                if weather_location:
                    break

    if weather_location:
        lat, lon = weather_location["latitude"], weather_location["longitude"]
        loc_name = weather_location["name"]

        if "weather_current" in sources:
            tasks["weather_current"] = meteo.get_current_weather(lat, lon, loc_name)

        if "weather_forecast" in sources:
            tasks["weather_forecast"] = meteo.get_forecast(lat, lon, 7, loc_name)

        if "temperature_data" in sources:
            wp = intent.weather_params
            today = date.today()
            sy = wp.start_year or (today.year - 1)
            ey = wp.end_year or today.year
            tasks["temperature_data"] = meteo.get_temperature_summary(
                lat, lon, f"{sy}-01-01", f"{min(ey, today.year)}-{today.month:02d}-{today.day:02d}", loc_name
            )

        if "rainfall_data" in sources:
            wp = intent.weather_params
            today = date.today()
            sy = wp.start_year or (today.year - 1)
            ey = wp.end_year or today.year
            tasks["rainfall_data"] = meteo.get_rainfall_summary(
                lat, lon, f"{sy}-01-01", f"{min(ey, today.year)}-{today.month:02d}-{today.day:02d}", loc_name
            )

    # ── Execute all fetches in parallel ───────────────────────────────────
    raw_data = {}
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error("Fetch error for %s: %s", name, result)
                state["errors"].append(f"Failed to fetch {name}: {result}")
                raw_data[name] = []
            else:
                # Handle both ApiResponse and WeatherResponse
                records = getattr(result, "records", result) if not isinstance(result, list) else result
                if isinstance(records, list):
                    raw_data[name] = records
                else:
                    raw_data[name] = []

    elapsed = (time.monotonic() - start) * 1000
    total_records = sum(len(v) for v in raw_data.values())
    logger.info("Fetched %d total records from %d sources (%.0fms)", total_records, len(raw_data), elapsed)

    state["raw_data"] = raw_data
    state["metadata"] = {
        "records_fetched": total_records,
        "sources": list(raw_data.keys()),
        "weather_location": weather_location,
        "fetch_date": datetime.now().isoformat(),
    }
    state["timing"]["fetch_data"] = round(elapsed, 1)
    return state


# ══════════════════════════════════════════════════════════════════════════════
# NODE 4: Validate Data
# ══════════════════════════════════════════════════════════════════════════════

async def validate_data(state: AgentState) -> AgentState:
    """Validate fetched data quality and decide if sufficient."""
    start = time.monotonic()
    raw_data = state["raw_data"]
    quality = {}

    for source_id, records in raw_data.items():
        dq = DataQuality(source_id=source_id, record_count=len(records), has_data=len(records) > 0)

        if not records:
            dq.notes.append("No records returned")
        elif len(records) < 3:
            dq.notes.append(f"Very few records ({len(records)}), results may be incomplete")

        # Check data freshness
        if source_id in ("weather_current", "weather_forecast"):
            dq.freshness = "live"
        elif source_id in ("temperature_data", "rainfall_data"):
            dq.freshness = "recent"
        elif source_id in ("daily_prices", "variety_prices"):
            dq.freshness = "today"
        else:
            dq.freshness = "historical"

        quality[source_id] = dq.model_dump()

    elapsed = (time.monotonic() - start) * 1000
    state["data_quality"] = quality
    state["timing"]["validate_data"] = round(elapsed, 1)

    has_any_data = any(dq.get("has_data", False) for dq in quality.values())
    logger.info("Data validation: %d sources, has_data=%s (%.0fms)",
                len(quality), has_any_data, elapsed)

    return state


# ══════════════════════════════════════════════════════════════════════════════
# NODE 5: Analyze Data
# ══════════════════════════════════════════════════════════════════════════════

async def analyze_data(state: AgentState) -> AgentState:
    """Perform advanced analysis based on query type."""
    start = time.monotonic()
    intent = state["intent"]
    raw_data = state["raw_data"]
    analysis = {"query_type": intent.query_type, "insights": [], "structured_data": {}}

    production_data = raw_data.get("crop_production", [])
    daily_price_data = raw_data.get("daily_prices", [])
    variety_price_data = raw_data.get("variety_prices", [])
    price_data = daily_price_data or variety_price_data
    temp_data = raw_data.get("temperature_data", [])
    rainfall_data = raw_data.get("rainfall_data", [])
    weather_current = raw_data.get("weather_current", [])
    weather_forecast = raw_data.get("weather_forecast", [])

    try:
        # ── COMPARISON ────────────────────────────────────────────────────
        if intent.query_type == "comparison":
            if production_data:
                states = list(set(
                    r.get("State_Name", r.get("state_name", ""))
                    for r in production_data if r.get("State_Name") or r.get("state_name")
                ))
                if len(states) >= 2:
                    state_a, state_b = states[0], states[1]
                    data_a = [r for r in production_data if r.get("State_Name", r.get("state_name")) == state_a]
                    data_b = [r for r in production_data if r.get("State_Name", r.get("state_name")) == state_b]
                    comparison = generate_comparative_summary(
                        state_a, state_b, data_a, data_b, metric_field="Production", entity_type="state"
                    )
                    analysis["insights"].append({
                        "type": "state_comparison",
                        "title": f"Production Comparison: {state_a} vs {state_b}",
                        "data": comparison,
                    })
                    analysis["structured_data"]["comparison"] = comparison

            if price_data and price_data[0].get("state"):
                price_by_state = aggregate_by_group(price_data, "state", "modal_price", "mean")
                analysis["structured_data"]["price_comparison"] = price_by_state

        # ── TREND ─────────────────────────────────────────────────────────
        elif intent.query_type == "trend":
            if production_data and "Crop_Year" in production_data[0]:
                trend = calculate_trend(production_data, "Crop_Year", "Production")
                if "direction" in trend:
                    analysis["insights"].append({
                        "type": "production_trend",
                        "title": "Production Trend Analysis",
                        "data": trend,
                        "summary": f'Production is {trend["direction"]} with {trend["percent_change"]}% change over {trend["data_points"]} years',
                    })
                    analysis["structured_data"]["trend"] = trend
                    yoy = calculate_year_over_year_growth(production_data, "Crop_Year", "Production")
                    if yoy:
                        analysis["structured_data"]["year_over_year"] = yoy

        # ── CORRELATION ───────────────────────────────────────────────────
        elif intent.query_type == "correlation":
            if production_data and rainfall_data:
                year_field = "Year" if "Year" in production_data[0] else "Crop_Year"
                correlation = correlate_production_with_climate(
                    production_data, rainfall_data,
                    production_field="Production", climate_field="precipitation_sum",
                    year_field=year_field,
                )
                if "coefficient" in correlation:
                    analysis["insights"].append({
                        "type": "climate_correlation",
                        "title": "Production-Rainfall Correlation",
                        "data": correlation,
                        "summary": f'{correlation["strength"].capitalize()} {correlation["direction"]} correlation (r={correlation["coefficient"]})',
                    })
                    analysis["structured_data"]["correlation"] = correlation

        # ── POLICY ────────────────────────────────────────────────────────
        elif intent.query_type == "policy":
            if production_data:
                crops = list(set(
                    r.get("Crop", r.get("crop", ""))
                    for r in production_data if r.get("Crop") or r.get("crop")
                ))
                if len(crops) >= 2 and rainfall_data:
                    crop_a, crop_b = crops[0], crops[1]
                    crop_a_data = [r for r in production_data if r.get("Crop", r.get("crop")) == crop_a]
                    crop_b_data = [r for r in production_data if r.get("Crop", r.get("crop")) == crop_b]
                    region = production_data[0].get("State_Name", production_data[0].get("state_name", "the region"))
                    policy_args = generate_policy_arguments(
                        crop_a, crop_b, region,
                        {"crop_a": crop_a_data, "crop_b": crop_b_data},
                        {"rainfall": rainfall_data},
                    )
                    analysis["insights"].append({
                        "type": "policy_recommendation",
                        "title": f"Policy Arguments: {crop_a} vs {crop_b}",
                        "data": policy_args,
                    })
                    analysis["structured_data"]["policy"] = policy_args

        # ── RANKING ───────────────────────────────────────────────────────
        elif intent.query_type == "ranking":
            if production_data and "Production" in production_data[0]:
                top = top_n_ranking(production_data, "Production", n=10, ascending=False)
                if top:
                    analysis["insights"].append({
                        "type": "production_ranking", "title": "Top Producers", "data": top,
                    })
                    analysis["structured_data"]["rankings"] = top
            elif price_data and "modal_price" in price_data[0]:
                top = top_n_ranking(price_data, "modal_price", n=10, ascending=False)
                if top:
                    analysis["insights"].append({"type": "price_ranking", "title": "Highest Prices", "data": top})
                    analysis["structured_data"]["rankings"] = top

        # ── WEATHER (current / forecast) ──────────────────────────────────
        elif intent.query_type in ("current_weather", "forecast"):
            if weather_current:
                analysis["structured_data"]["current_weather"] = weather_current[0]
            if weather_forecast:
                analysis["structured_data"]["forecast"] = weather_forecast[:7]

        # ── General aggregations (always useful) ──────────────────────────
        if production_data and len(production_data) > 1:
            if "State_Name" in production_data[0] and "Production" in production_data[0]:
                analysis["structured_data"]["state_totals"] = aggregate_by_group(
                    production_data, "State_Name", "Production", "sum"
                )
            if "Season" in production_data[0] and "Production" in production_data[0]:
                analysis["structured_data"]["season_totals"] = aggregate_by_group(
                    production_data, "Season", "Production", "sum"
                )

        if price_data:
            state_field = "state" if "state" in price_data[0] else "State"
            price_field = "modal_price" if "modal_price" in price_data[0] else "Modal_Price"
            if state_field in price_data[0] and price_field in price_data[0]:
                analysis["structured_data"]["avg_prices_by_state"] = aggregate_by_group(
                    price_data, state_field, price_field, "mean"
                )

        # Weather summaries
        if temp_data:
            analysis["structured_data"]["temperature_summary"] = {
                "records": len(temp_data),
                "sample": temp_data[:5],
            }
        if rainfall_data:
            analysis["structured_data"]["rainfall_summary"] = {
                "records": len(rainfall_data),
                "sample": rainfall_data[:5],
            }

    except Exception as e:
        logger.error("Analysis error: %s", e, exc_info=True)
        state["errors"].append(f"Analysis failed: {e}")

    elapsed = (time.monotonic() - start) * 1000
    state["analysis"] = analysis
    state["timing"]["analyze_data"] = round(elapsed, 1)
    return state


# ══════════════════════════════════════════════════════════════════════════════
# NODE 6: Generate Answer
# ══════════════════════════════════════════════════════════════════════════════

async def generate_answer(state: AgentState) -> AgentState:
    """Generate final answer using LLM with data and analysis."""
    start = time.monotonic()
    intent = state.get("intent")
    raw_data = state.get("raw_data", {})
    analysis = state.get("analysis") or {}
    data_quality = state.get("data_quality", {})
    errors = state.get("errors", [])

    total_records = sum(len(v) for v in raw_data.values())

    # ── Handle no-data cases ──────────────────────────────────────────────
    if not raw_data or total_records == 0:
        needs_data = intent and any([
            intent.daily_price_params, intent.variety_price_params,
            intent.production_params, intent.weather_params,
        ]) if intent else False

        if needs_data:
            error_details = "; ".join(errors) if errors else "No specific error"
            state["answer"] = f"""I couldn't find data matching your query. {f'Technical details: {error_details}' if errors else ''}

This could be because:
- The specific combination of filters didn't match any records
- The data source might be temporarily unavailable
- The state/district/crop names might need different spelling

Try:
- Broadening your search (e.g., just state without district)
- Checking spelling of state/district/crop names
- Asking about a different time period

Example queries that work well:
- "What is rice production in Punjab?"
- "Current weather in Maharashtra"
- "Compare wheat prices across states"
- "Rainfall forecast for UP" """
            state["timing"]["generate_answer"] = round((time.monotonic() - start) * 1000, 1)
            return state
        else:
            # General question
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant specializing in Indian agriculture.
Answer general questions about agricultural practices, crop types, farming knowledge,
agricultural policies, and climate impacts on agriculture.
If the question requires specific data, explain what data you could fetch and suggest
rephrasing the question. Be helpful, concise, and professional."""),
                ("human", "{question}")
            ])
            chain = prompt | get_llm() | StrOutputParser()
            state["answer"] = await chain.ainvoke({"question": state["question"]})
            state["timing"]["generate_answer"] = round((time.monotonic() - start) * 1000, 1)
            return state

    # ── Build context for data-driven answer ──────────────────────────────
    context_parts = []
    today = date.today()

    # Data quality notes
    quality_notes = []
    for src_id, dq in data_quality.items():
        if dq.get("notes"):
            quality_notes.extend(dq["notes"])
        if dq.get("freshness") == "live":
            quality_notes.append(f"{src_id}: live data")

    if quality_notes:
        context_parts.append("## Data Quality Notes")
        for note in quality_notes:
            context_parts.append(f"- {note}")

    # Raw data samples
    for source, data in raw_data.items():
        if data:
            context_parts.append(f"## {source} ({len(data)} records)")
            context_parts.append(str(data[:10]))

    # Analysis results
    if analysis:
        context_parts.append("\n## Analysis")
        context_parts.append(str(analysis))

    context = "\n\n".join(context_parts) if context_parts else "No data available"

    # ── Generate answer ───────────────────────────────────────────────────
    query_type = intent.query_type if intent else "general"

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an Agriculture Data Analyst providing insights on Indian agriculture.
Today is {today.isoformat()}.

Query Type: {query_type}

IMPORTANT Instructions:
- DO NOT mention technical data source names (like "rainfall_subdivisions", "crop_production", etc.)
- Present findings naturally without referencing database/API names
- Use actual numbers, states, districts, and years from the provided data
- Be specific and data-driven
- When showing weather data, present it in a user-friendly format (°C, mm, etc.)

Response Guidelines:
- For comparisons: show side-by-side data with differences and percentages
- For trends: mention direction, growth rate, time period, and specific values
- For correlations: explain strength, direction, and practical implications
- For rankings: list top items with their specific values
- For policy: provide data-backed arguments with concrete numbers
- For weather/forecast: present conditions clearly with agricultural implications
- For current prices: present today's market prices clearly

Data freshness: This data was fetched in real-time on {today.isoformat()}.
Be concise, precise, and professional."""),
        ("human", "Question: {question}\n\nData:\n{context}")
    ])

    chain = prompt | get_llm() | StrOutputParser()
    answer = await chain.ainvoke({"question": state["question"], "context": context})

    elapsed = (time.monotonic() - start) * 1000
    state["answer"] = answer
    state["timing"]["generate_answer"] = round(elapsed, 1)
    return state
