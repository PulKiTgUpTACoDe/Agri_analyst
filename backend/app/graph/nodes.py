import asyncio, logging, time
from datetime import date, datetime, timedelta
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
from app.utils.aggregation import top_n_ranking, calculate_trend, aggregate_by_group, calculate_year_over_year_growth
from app.utils.correlation import correlate_production_with_climate
from app.utils.policy_synthesis import generate_policy_arguments, generate_comparative_summary

logger = logging.getLogger("agri.nodes")
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        s = get_settings()
        _llm = ChatGoogleGenerativeAI(model=s.GEMINI_MODEL, google_api_key=s.GOOGLE_API_KEY,
                                       temperature=s.GEMINI_TEMPERATURE, max_output_tokens=s.GEMINI_MAX_TOKENS)
    return _llm

TEMP_KW = {"temperature", "temp", "heat", "cold", "hot", "warm", "cool"}
RAIN_KW = {"rainfall", "rain", "precipitation", "monsoon", "flood", "drought"}

async def detect_intent(state: AgentState) -> AgentState:
    start = time.monotonic()
    today = date.today()
    yr = today.year
    week_ago = (today - timedelta(days=7)).isoformat()

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an intent classifier for an Indian agriculture data system.
Today: {today.isoformat()}. Year: {yr}.

Output JSON matching QueryIntent schema.

Query types: comparison, trend, correlation, policy, ranking, forecast, current_weather, general

Sources:
1. daily_price_params: mandi prices (state, district, market, commodity, variety)
2. variety_price_params: variety prices (state, district, commodity)
3. production_params: crop production from 1997 (state_name, district_name, crop, crop_year, season)
4. weather_params: weather (state, district, subdivision, start_year, end_year, start_date, end_date, include_forecast, include_current)

Weather rules:
- Use start_date/end_date (YYYY-MM-DD) for precise ranges, overrides year fields
- "recent"/"latest" without period = last 7 days: start_date="{week_ago}", end_date="{today.isoformat()}"
- "current weather"/"today" = include_current=true, no date fields
- "forecast" = include_forecast=true, no date fields
- start_year/end_year only for multi-year analysis
- Set metrics: "temperature", "rainfall", or both"""),
        ("human", "{question}")
    ])
    chain = prompt | get_llm().with_structured_output(QueryIntent)
    intent = await chain.ainvoke({"question": state["question"]})
    elapsed = (time.monotonic() - start) * 1000
    logger.info("Intent: type=%s entities=%s (%.0fms)", intent.query_type, intent.entities, elapsed)
    state["intent"] = intent
    state["timing"]["detect_intent"] = round(elapsed, 1)
    return state

async def select_sources(state: AgentState) -> AgentState:
    start = time.monotonic()
    intent = state["intent"]
    sources = []
    if intent.daily_price_params: sources.append("daily_prices")
    if intent.variety_price_params: sources.append("variety_prices")
    if intent.production_params: sources.append("crop_production")

    if intent.weather_params:
        wp = intent.weather_params
        if wp.include_current: sources.append("weather_current")
        if wp.include_forecast: sources.append("weather_forecast")
        if wp.start_year or wp.end_year or wp.start_date or wp.end_date:
            metrics = {m.lower() for m in intent.metrics}
            q = state["question"].lower()
            has_temp = bool(metrics & TEMP_KW) or any(k in q for k in TEMP_KW)
            has_rain = bool(metrics & RAIN_KW) or any(k in q for k in RAIN_KW)
            if has_temp: sources.append("temperature_data")
            if has_rain: sources.append("rainfall_data")
            if not has_temp and not has_rain: sources.append("temperature_data")

    state["sources_selected"] = sources
    state["timing"]["select_sources"] = round((time.monotonic() - start) * 1000, 1)
    return state

def _resolve_dates(wp) -> tuple[str, str]:
    today = date.today()
    if wp.start_date and wp.end_date:
        return wp.start_date, min(wp.end_date, today.isoformat())
    if wp.start_date:
        return wp.start_date, today.isoformat()
    if wp.end_date:
        return (date.fromisoformat(wp.end_date) - timedelta(days=30)).isoformat(), wp.end_date
    if wp.start_year and wp.end_year:
        end = today.isoformat() if wp.end_year >= today.year else f"{wp.end_year}-12-31"
        return f"{wp.start_year}-01-01", end
    if wp.start_year:
        return f"{wp.start_year}-01-01", today.isoformat()
    if wp.end_year:
        return f"{wp.end_year}-01-01", f"{min(wp.end_year, today.year)}-12-31"
    return (today - timedelta(days=30)).isoformat(), today.isoformat()

async def fetch_data(state: AgentState) -> AgentState:
    start = time.monotonic()
    intent = state["intent"]
    sources = state.get("sources_selected", [])
    client = get_client()
    meteo = get_meteo_client()
    cache = get_cache()
    reg = get_registry()
    client.set_cache(cache)
    meteo.set_cache(cache)
    tasks = {}

    if "daily_prices" in sources and intent.daily_price_params:
        p = intent.daily_price_params
        ds = reg.get_source("daily_prices")
        tasks["daily_prices"] = client.fetch(ds.resource_id, {"state.keyword": p.state, "district": p.district,
                                                               "market": p.market, "commodity": p.commodity, "variety": p.variety})
    if "variety_prices" in sources and intent.variety_price_params:
        p = intent.variety_price_params
        ds = reg.get_source("variety_prices")
        tasks["variety_prices"] = client.fetch(ds.resource_id, {"State": p.state, "District": p.district, "Commodity": p.commodity})
    if "crop_production" in sources and intent.production_params:
        p = intent.production_params
        ds = reg.get_source("crop_production")
        tasks["crop_production"] = client.fetch(ds.resource_id, {"state_name": p.state_name, "district_name": p.district_name,
                                                                  "crop": p.crop, "crop_year": p.crop_year, "season": p.season}, limit=5000)

    weather_location = None
    if intent.weather_params:
        wp = intent.weather_params
        weather_location = resolve_location(state=wp.state, district=wp.district, subdivision=wp.subdivision)
        if not weather_location:
            for e in intent.entities:
                weather_location = resolve_location(state=e)
                if weather_location: break

    if weather_location:
        lat, lon, name = weather_location["latitude"], weather_location["longitude"], weather_location["name"]
        if "weather_current" in sources:
            tasks["weather_current"] = meteo.get_current_weather(lat, lon, name)
        if "weather_forecast" in sources:
            tasks["weather_forecast"] = meteo.get_forecast(lat, lon, 7, name)
        if "temperature_data" in sources:
            s, e = _resolve_dates(intent.weather_params)
            tasks["temperature_data"] = meteo.get_temperature_summary(lat, lon, s, e, name)
        if "rainfall_data" in sources:
            s, e = _resolve_dates(intent.weather_params)
            tasks["rainfall_data"] = meteo.get_rainfall_summary(lat, lon, s, e, name)

    raw_data = {}
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for k, r in zip(tasks.keys(), results):
            if isinstance(r, Exception):
                logger.error("Fetch error %s: %s", k, r)
                state["errors"].append(f"Failed {k}: {r}")
                raw_data[k] = []
            else:
                records = getattr(r, "records", r) if not isinstance(r, list) else r
                raw_data[k] = records if isinstance(records, list) else []

    total = sum(len(v) for v in raw_data.values())
    state["raw_data"] = raw_data
    state["metadata"] = {"records_fetched": total, "sources": list(raw_data.keys()),
                          "weather_location": weather_location, "fetch_date": datetime.now().isoformat()}
    state["timing"]["fetch_data"] = round((time.monotonic() - start) * 1000, 1)
    return state

async def validate_data(state: AgentState) -> AgentState:
    start = time.monotonic()
    quality = {}
    freshness_map = {"weather_current": "live", "weather_forecast": "live", "temperature_data": "recent",
                     "rainfall_data": "recent", "daily_prices": "today", "variety_prices": "today"}
    for sid, records in state["raw_data"].items():
        dq = DataQuality(source_id=sid, record_count=len(records), has_data=len(records) > 0,
                         freshness=freshness_map.get(sid, "historical"))
        if not records: dq.notes.append("No records")
        quality[sid] = dq.model_dump()
    state["data_quality"] = quality
    state["timing"]["validate_data"] = round((time.monotonic() - start) * 1000, 1)
    return state

def _get(r, *keys):
    for k in keys:
        v = r.get(k)
        if v: return v
    return ""

async def analyze_data(state: AgentState) -> AgentState:
    start = time.monotonic()
    intent = state["intent"]
    raw = state["raw_data"]
    analysis = {"query_type": intent.query_type, "insights": [], "structured_data": {}}
    prod = raw.get("crop_production", [])
    price = raw.get("daily_prices", []) or raw.get("variety_prices", [])
    temp = raw.get("temperature_data", [])
    rain = raw.get("rainfall_data", [])
    current = raw.get("weather_current", [])
    forecast = raw.get("weather_forecast", [])

    try:
        if intent.query_type == "comparison" and prod:
            states = list({_get(r, "State_Name", "state_name") for r in prod if _get(r, "State_Name", "state_name")})
            if len(states) >= 2:
                a, b = states[0], states[1]
                da = [r for r in prod if _get(r, "State_Name", "state_name") == a]
                db = [r for r in prod if _get(r, "State_Name", "state_name") == b]
                comp = generate_comparative_summary(a, b, da, db, metric_field="Production", entity_type="state")
                analysis["insights"].append({"type": "comparison", "title": f"{a} vs {b}", "data": comp})
                analysis["structured_data"]["comparison"] = comp

        elif intent.query_type == "trend" and prod and "Crop_Year" in prod[0]:
            trend = calculate_trend(prod, "Crop_Year", "Production")
            if "direction" in trend:
                analysis["insights"].append({"type": "trend", "title": "Production Trend", "data": trend})
                analysis["structured_data"]["trend"] = trend
                yoy = calculate_year_over_year_growth(prod, "Crop_Year", "Production")
                if yoy: analysis["structured_data"]["year_over_year"] = yoy

        elif intent.query_type == "correlation" and prod and rain:
            yf = "Year" if "Year" in prod[0] else "Crop_Year"
            corr = correlate_production_with_climate(prod, rain, "Production", "precipitation_sum", yf)
            if "coefficient" in corr:
                analysis["insights"].append({"type": "correlation", "title": "Production-Rainfall", "data": corr})
                analysis["structured_data"]["correlation"] = corr

        elif intent.query_type == "policy" and prod and len({_get(r, "Crop", "crop") for r in prod if _get(r, "Crop", "crop")}) >= 2:
            crops = list({_get(r, "Crop", "crop") for r in prod if _get(r, "Crop", "crop")})
            ca, cb = crops[0], crops[1]
            region = _get(prod[0], "State_Name", "state_name") or "region"
            pa = generate_policy_arguments(ca, cb, region,
                {"crop_a": [r for r in prod if _get(r, "Crop", "crop") == ca],
                 "crop_b": [r for r in prod if _get(r, "Crop", "crop") == cb]}, {"rainfall": rain})
            analysis["insights"].append({"type": "policy", "title": f"{ca} vs {cb}", "data": pa})
            analysis["structured_data"]["policy"] = pa

        elif intent.query_type == "ranking":
            if prod and "Production" in prod[0]:
                top = top_n_ranking(prod, "Production", n=10, ascending=False)
                if top: analysis["structured_data"]["rankings"] = top
            elif price:
                pf = "modal_price" if "modal_price" in price[0] else "Modal_Price"
                if pf in price[0]:
                    top = top_n_ranking(price, pf, n=10, ascending=False)
                    if top: analysis["structured_data"]["rankings"] = top

        elif intent.query_type in ("current_weather", "forecast"):
            if current: analysis["structured_data"]["current_weather"] = current[0]
            if forecast: analysis["structured_data"]["forecast"] = forecast[:7]

        if prod and len(prod) > 1 and "State_Name" in prod[0] and "Production" in prod[0]:
            analysis["structured_data"]["state_totals"] = aggregate_by_group(prod, "State_Name", "Production", "sum")
        if price:
            sf = "state" if "state" in price[0] else "State"
            pf = "modal_price" if "modal_price" in price[0] else "Modal_Price"
            if sf in price[0] and pf in price[0]:
                analysis["structured_data"]["avg_prices"] = aggregate_by_group(price, sf, pf, "mean")
        if temp: analysis["structured_data"]["temperature"] = {"records": len(temp), "sample": temp[:5]}
        if rain: analysis["structured_data"]["rainfall"] = {"records": len(rain), "sample": rain[:5]}
    except Exception as e:
        logger.error("Analysis error: %s", e, exc_info=True)
        state["errors"].append(f"Analysis failed: {e}")

    state["analysis"] = analysis
    state["timing"]["analyze_data"] = round((time.monotonic() - start) * 1000, 1)
    return state

async def generate_answer(state: AgentState) -> AgentState:
    start = time.monotonic()
    intent = state.get("intent")
    raw_data = state.get("raw_data", {})
    analysis = state.get("analysis") or {}
    total = sum(len(v) for v in raw_data.values())
    today = date.today()

    if not raw_data or total == 0:
        has_params = intent and any([intent.daily_price_params, intent.variety_price_params,
                                     intent.production_params, intent.weather_params]) if intent else False
        if has_params:
            state["answer"] = "I couldn't find data matching your query. Try broadening your search or check spelling of state/district/crop names."
        else:
            chain = ChatPromptTemplate.from_messages([
                ("system", "You are an AI assistant specializing in Indian agriculture. Be concise and professional."),
                ("human", "{question}")
            ]) | get_llm() | StrOutputParser()
            state["answer"] = await chain.ainvoke({"question": state["question"]})
        state["timing"]["generate_answer"] = round((time.monotonic() - start) * 1000, 1)
        return state

    ctx = []
    for src, data in raw_data.items():
        if data:
            ctx.append(f"## {src} ({len(data)} records)\n{str(data[:10])}")
    if analysis:
        ctx.append(f"\n## Analysis\n{str(analysis)}")

    qt = intent.query_type if intent else "general"
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""Agriculture Data Analyst. Today: {today.isoformat()}.
Query Type: {qt}

Rules:
- Don't mention technical source names
- Use actual numbers from the data
- Present weather in user-friendly format (°C, mm)
- Be concise and data-driven
- Data fetched in real-time on {today.isoformat()}"""),
        ("human", "Question: {question}\n\nData:\n{context}")
    ])
    chain = prompt | get_llm() | StrOutputParser()
    state["answer"] = await chain.ainvoke({"question": state["question"], "context": "\n\n".join(ctx)})
    state["timing"]["generate_answer"] = round((time.monotonic() - start) * 1000, 1)
    return state
