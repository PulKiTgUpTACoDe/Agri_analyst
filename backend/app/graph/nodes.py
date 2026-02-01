"""LangGraph node functions."""
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.graph.state import AgentState
from app.core.config import get_settings
from app.core.schemas import QueryIntent
from app.core.api_client import get_client
from app.utils.aggregation import (
    top_n_ranking,
    calculate_trend,
    aggregate_by_group,
    aggregate_multi_year_average,
    calculate_year_over_year_growth
)
from app.utils.correlation import (
    correlate_production_with_climate,
    identify_optimal_conditions,
    compare_climate_impact
)
from app.utils.policy_synthesis import (
    generate_policy_arguments,
    generate_comparative_summary
)

# Vector store import (lazy loaded)
def get_vector_store_lazy():
    """Lazy load vector store to avoid errors if not configured."""
    try:
        from app.db.vector_store import get_vector_store
        return get_vector_store()
    except Exception as e:
        print(f"[VECTOR_STORE] Not available: {e}")
        return None


 


async def detect_intent(state: AgentState) -> AgentState:
    """Detect query intent and extract parameters using LLM."""
    settings = get_settings()
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Extract query intent and parameters. Output JSON matching QueryIntent schema.
        
Query types:
- comparison: comparing entities (states/crops)
- trend: analyzing changes over time
- correlation: relationships between variables
- policy: recommendations/arguments
- ranking: top/bottom performers
- general: simple factual queries

Data sources to consider:
1. daily_price_params: For daily market prices (state_keyword, district, market, commodity, variety, grade)
2. variety_price_params: For variety-wise prices (State, District, Commodity, Arrival_Date) - note capital letters
3. production_params: For crop production (state_name, district_name, crop, crop_year, season, area_, production_)
4. temperature_params: For temperature series (year, seasonal filters)
5. rainfall_params: For rainfall subdivisions (subdivision, year)

Extract relevant params for each source based on the question."""),
        ("human", "{question}")
    ])
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.GEMINI_TEMPERATURE,
        max_output_tokens=settings.GEMINI_MAX_TOKENS
    )
    chain = prompt | llm.with_structured_output(QueryIntent)
    intent = await chain.ainvoke({"question": state["question"]})
    
    state["intent"] = intent
    return state


async def fetch_data(state: AgentState) -> AgentState:
    """Fetch data from relevant sources based on intent."""
    intent = state["intent"]
    settings = get_settings()
    client = get_client()
    
    tasks = {}
    
    # 1. Daily Prices
    if intent.daily_price_params:
        filters = {
            "state.keyword": intent.daily_price_params.state_keyword or intent.daily_price_params.state,
            "district": intent.daily_price_params.district,
            "market": intent.daily_price_params.market,
            "commodity": intent.daily_price_params.commodity,
            "variety": intent.daily_price_params.variety,
            "grade": intent.daily_price_params.grade
        }
        tasks["daily_prices"] = client.fetch(
            settings.daily_prices_endpoint,
            {k: v for k, v in filters.items() if v},
            intent.daily_price_params.limit
        )
    
    # 2. Variety Prices
    if intent.variety_price_params:
        filters = {
            "State": intent.variety_price_params.State or intent.variety_price_params.state,
            "District": intent.variety_price_params.District or intent.variety_price_params.district,
            "Commodity": intent.variety_price_params.Commodity,
            "Arrival_Date": intent.variety_price_params.Arrival_Date
        }
        tasks["variety_prices"] = client.fetch(
            settings.variety_prices_endpoint,
            {k: v for k, v in filters.items() if v},
            intent.variety_price_params.limit
        )
    
    # 3. Crop Production
    if intent.production_params:
        filters = {
            "state_name": intent.production_params.state_name,
            "district_name": intent.production_params.district_name,
            "crop": intent.production_params.crop,
            "crop_year": intent.production_params.crop_year,
            "season": intent.production_params.season,
            "area_": intent.production_params.area_,
            "production_": intent.production_params.production_
        }
        tasks["crop_production"] = client.fetch(
            settings.crop_production_endpoint,
            {k: v for k, v in filters.items() if v},
            intent.production_params.limit
        )
    
    # 4. Temperature Series
    if intent.temperature_params:
        filters = {
            "year": intent.temperature_params.year,
            "_annual": intent.temperature_params.annual,
            "_jan_feb": intent.temperature_params.jan_feb,
            "_mar_may": intent.temperature_params.mar_may,
            "_jun_sep": intent.temperature_params.jun_sep,
            "_oct_dec": intent.temperature_params.oct_dec
        }
        tasks["temperature_series"] = client.fetch(
            settings.temperature_endpoint,
            {k: v for k, v in filters.items() if v},
            intent.temperature_params.limit
        )
    
    # 5. Rainfall Subdivisions
    if intent.rainfall_params:
        filters = {
            "subdivision": intent.rainfall_params.subdivision,
            "year": intent.rainfall_params.year
        }
        tasks["rainfall_subdivisions"] = client.fetch(
            settings.rainfall_endpoint,
            {k: v for k, v in filters.items() if v},
            intent.rainfall_params.limit
        )
    
    # Execute all fetches in parallel
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        raw_data = {
            name: (result if isinstance(result, list) else [])
            for name, result in zip(tasks.keys(), results)
        }
    else:
        raw_data = {}
    
    state["raw_data"] = raw_data
    state["metadata"] = {
        "records_fetched": sum(len(v) for v in raw_data.values()),
        "sources": list(raw_data.keys())
    }
    return state


async def analyze_data(state: AgentState) -> AgentState:
    """Perform advanced analysis based on query type."""
    intent = state["intent"]
    raw_data = state["raw_data"]
    analysis = {
        'query_type': intent.query_type,
        'insights': [],
        'structured_data': {}
    }
    
    production_data = raw_data.get('crop_production', [])
    rainfall_data = raw_data.get('rainfall_subdivisions', [])
    daily_price_data = raw_data.get('daily_prices', [])
    variety_price_data = raw_data.get('variety_prices', [])
    price_data = daily_price_data or variety_price_data
    temp_data = raw_data.get('temperature_series', [])
    
    # COMPARISON ANALYSIS
    if intent.query_type == "comparison":
        if production_data:
            states = list(set(r.get('State_Name', r.get('state_name', '')) for r in production_data if r.get('State_Name') or r.get('state_name')))
            
            if len(states) >= 2:
                state_a, state_b = states[0], states[1]
                data_a = [r for r in production_data if r.get('State_Name', r.get('state_name')) == state_a]
                data_b = [r for r in production_data if r.get('State_Name', r.get('state_name')) == state_b]
                
                comparison = generate_comparative_summary(
                    state_a, state_b, data_a, data_b,
                    metric_field='Production',
                    entity_type='state'
                )
                
                analysis['insights'].append({
                    'type': 'state_comparison',
                    'title': f'Production Comparison: {state_a} vs {state_b}',
                    'data': comparison
                })
                analysis['structured_data']['comparison'] = comparison
        
        # Price comparison if available
        if price_data and 'state' in price_data[0]:
            price_by_state = aggregate_by_group(price_data, 'state', 'modal_price', 'mean')
            analysis['structured_data']['price_comparison'] = price_by_state
    
    # TREND ANALYSIS
    elif intent.query_type == "trend":
        if production_data and 'Crop_Year' in production_data[0]:
            trend = calculate_trend(production_data, 'Crop_Year', 'Production')
            
            if 'direction' in trend:
                analysis['insights'].append({
                    'type': 'production_trend',
                    'title': 'Production Trend Analysis',
                    'data': trend,
                    'summary': f'Production trend is {trend["direction"]} with {trend["percent_change"]}% change over {trend["data_points"]} years'
                })
                analysis['structured_data']['trend'] = trend
                
                # Year-over-year growth
                yoy_growth = calculate_year_over_year_growth(
                    production_data, 'Crop_Year', 'Production'
                )
                if yoy_growth:
                    analysis['structured_data']['year_over_year'] = yoy_growth
    
    # CORRELATION ANALYSIS
    elif intent.query_type == "correlation":
        if production_data and rainfall_data:
            year_field = 'Year' if 'Year' in production_data[0] else 'Crop_Year'
            correlation = correlate_production_with_climate(
                production_data,
                rainfall_data,
                production_field='Production',
                climate_field='Rainfall',
                year_field=year_field
            )
            
            if 'coefficient' in correlation:
                analysis['insights'].append({
                    'type': 'climate_correlation',
                    'title': 'Production-Climate Correlation',
                    'data': correlation,
                    'summary': f'{correlation["strength"].capitalize()} {correlation["direction"]} correlation (r={correlation["coefficient"]})'
                })
                analysis['structured_data']['correlation'] = correlation
                
                # Optimal conditions
                if len(production_data) >= 10:
                    optimal = identify_optimal_conditions(
                        production_data,
                        'Production',
                        'Rainfall' if 'Rainfall' in production_data[0] else 'rainfall',
                        top_n=10
                    )
                    if 'optimal_climate_range' in optimal:
                        analysis['structured_data']['optimal_conditions'] = optimal
    
    # POLICY ANALYSIS
    elif intent.query_type == "policy":
        if production_data:
            crops = list(set(r.get('Crop', r.get('crop', '')) for r in production_data if r.get('Crop') or r.get('crop')))
            
            if len(crops) >= 2 and rainfall_data:
                crop_a, crop_b = crops[0], crops[1]
                crop_a_data = [r for r in production_data if r.get('Crop', r.get('crop')) == crop_a]
                crop_b_data = [r for r in production_data if r.get('Crop', r.get('crop')) == crop_b]
                
                region = production_data[0].get('State_Name', production_data[0].get('state_name', 'the region'))
                
                policy_args = generate_policy_arguments(
                    crop_a, crop_b, region,
                    {'crop_a': crop_a_data, 'crop_b': crop_b_data},
                    {'rainfall': rainfall_data}
                )
                
                analysis['insights'].append({
                    'type': 'policy_recommendation',
                    'title': f'Policy Arguments: {crop_a} vs {crop_b}',
                    'data': policy_args
                })
                analysis['structured_data']['policy'] = policy_args
    
    # RANKING ANALYSIS
    elif intent.query_type == "ranking":
        if production_data and 'Production' in production_data[0]:
            top_producers = top_n_ranking(
                production_data,
                'Production',
                n=10,
                ascending=False
            )
            
            analysis['insights'].append({
                'type': 'production_ranking',
                'title': 'Top Producers',
                'data': top_producers,
                'summary': f'Top producer: {top_producers[0].get("District_Name", top_producers[0].get("State_Name", "Unknown"))} with {top_producers[0]["Production"]} tonnes'
            })
            analysis['structured_data']['rankings'] = top_producers
        
        # Price rankings if available
        elif price_data and 'modal_price' in price_data[0]:
            top_prices = top_n_ranking(price_data, 'modal_price', n=10, ascending=False)
            analysis['insights'].append({
                'type': 'price_ranking',
                'title': 'Highest Prices',
                'data': top_prices
            })
            analysis['structured_data']['rankings'] = top_prices
    
    # MULTI-YEAR AVERAGES (for any query with multiple years)
    if production_data and len(production_data) > 1:
        if 'Crop_Year' in production_data[0] and 'State_Name' in production_data[0]:
            multi_year_avg = aggregate_multi_year_average(
                production_data,
                'Production',
                ['State_Name']
            )
            if multi_year_avg:
                analysis['structured_data']['multi_year_averages'] = multi_year_avg
    
    # GENERAL AGGREGATIONS (always useful)
    if production_data:
        # State-wise totals
        if 'State_Name' in production_data[0] and 'Production' in production_data[0]:
            state_totals = aggregate_by_group(production_data, 'State_Name', 'Production', 'sum')
            analysis['structured_data']['state_totals'] = state_totals
        
        # Season-wise if available
        if 'Season' in production_data[0] and 'Production' in production_data[0]:
            season_totals = aggregate_by_group(production_data, 'Season', 'Production', 'sum')
            analysis['structured_data']['season_totals'] = season_totals
    
    if price_data:
        # Average prices by state
        if 'state' in price_data[0] and 'modal_price' in price_data[0]:
            avg_prices = aggregate_by_group(price_data, 'state', 'modal_price', 'mean')
            analysis['structured_data']['avg_prices_by_state'] = avg_prices
    
    state["analysis"] = analysis
    return state


async def retrieve_context(state: AgentState) -> AgentState:
    """Retrieve relevant context from vector store based on question.
    
    DISABLED for Vercel deployment - vector operations require local models.
    """
    # Vector store disabled for Vercel deployment
    state["context_docs"] = []
    return state


async def generate_answer(state: AgentState) -> AgentState:
    """Generate final answer using LLM with data and analysis."""
    intent = state.get("intent")
    raw_data = state.get("raw_data", {})
    analysis = state.get("analysis") or {}
    settings = get_settings()
    
    # Check if this is a general question (no data needed)
    total_records = sum(len(v) for v in raw_data.values())
    
    # Handle general questions without agricultural data
    if not raw_data or total_records == 0:
        # Check if we even tried to fetch data
        needs_data = intent and any([
            intent.daily_price_params,
            intent.variety_price_params,
            intent.production_params,
            intent.temperature_params,
            intent.rainfall_params
        ]) if intent else False
        
        if needs_data:
            # We tried to fetch data but got nothing
            state["answer"] = """I apologize, but I couldn't find any data matching your query in our databases. This could be due to:

- The specific combination of filters (state, district, crop, year, etc.) not having available data
- The data might not be available for the requested time period
- There might be a temporary issue with the data source

Please try:
- Broadening your search (e.g., remove specific district or year filters)
- Checking if the state/district/crop names are spelled correctly
- Asking about a different time period or region

Example queries that typically work:
- "What is rice production in Punjab?"
- "Show rainfall trends in Maharashtra"
- "Compare wheat prices in different states"""
            return state
        else:
            # General question - answer without data
            llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=settings.GEMINI_TEMPERATURE,
                google_api_key=settings.GOOGLE_API_KEY
            )
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant specializing in Indian agriculture. 
                
You can answer general questions about:
- Agricultural practices and techniques
- Crop types and their characteristics
- General farming knowledge
- Agricultural policies and schemes
- Climate and weather impacts on agriculture

If the question requires specific data (prices, production numbers, rainfall data), politely inform the user that you need more specific details to fetch the relevant data.

Be helpful, concise, and professional."""),
                ("human", "{question}")
            ])
            
            chain = prompt | llm | StrOutputParser()
            state["answer"] = await chain.ainvoke({"question": state["question"]})
            
            # Store this Q&A too!
            await store_qa_in_vectorstore(state)
            
            return state
    
    # Build context
    context_parts = []
    
    # Add vector store context (historical knowledge)
    context_docs = state.get("context_docs", [])
    if context_docs:
        context_parts.append("## Historical Context & Similar Queries")
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(f"{i}. {doc['content'][:200]}...")  # First 200 chars
    
    # Add current data
    for source, data in raw_data.items():
        if data:
            context_parts.append(f"## {source} ({len(data)} records)")
            context_parts.append(str(data[:5]))  # Sample  
    
    # Add analysis
    if analysis:
        context_parts.append("\n## Analysis")
        context_parts.append(str(analysis))
    
    context = "\n\n".join(context_parts) if context_parts else "No data available"
    
    # Initialize LLM for data-driven answers
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        temperature=settings.GEMINI_TEMPERATURE,
        google_api_key=settings.GOOGLE_API_KEY
    )
    
    # Generate answer
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an Agriculture Data Analyst providing insights on Indian agriculture.

Query Type: {intent.query_type}

IMPORTANT Instructions:
- DO NOT mention technical data source names (like "rainfall_subdivisions", "crop_production", etc.) in your response
- Present findings naturally without referencing database/API names
- Use actual numbers, states, districts, and years from the provided data
- Be specific and data-driven

Response Guidelines:
- For comparisons: show side-by-side data with differences and percentages
- For trends: mention direction, growth rate, time period, and specific values
- For correlations: explain strength, direction, and practical implications
- For rankings: list top items with their specific values
- For policy: provide data-backed arguments with concrete numbers
- Be concise, precise, and professional

Example (Good): "Rainfall in Maharashtra shows a decreasing trend from 920 mm in 2000 to 880 mm in 2020."
Example (Bad): "Based on data from rainfall_subdivisions, Maharashtra shows..."

Focus on delivering insights, not on explaining where the data came from."""),
        ("human", "Question: {question}\n\nData:\n{context}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    answer = await chain.ainvoke({"question": state["question"], "context": context})
    state["answer"] = answer
    
    # Store this Q&A pair in vector store for future retrievals
    await store_qa_in_vectorstore(state)
    
    return state


async def store_qa_in_vectorstore(state: AgentState):
    """Store question-answer pair in vector store for future retrieval.
    
    This builds a knowledge base of answered questions over time.
    Uses Pinecone's integrated embeddings (llama-text-embed-v2).
    """
    settings = get_settings()
    
    if not settings.PINECONE_API_KEY:
        print("[VECTOR_STORE] Skipping storage - no API key configured")
        return  # Skip if not configured
    
    try:
        # Import vector store functions
        from app.db.vector_store import add_texts
        
        question = state["question"]
        answer = state["answer"]
        intent = state.get("intent")
        metadata = state.get("metadata", {})
        
        # Create a document combining question and answer
        doc_text = f"Question: {question}\n\nAnswer: {answer}"
        
        # Prepare metadata (ensure all values are JSON-serializable)
        doc_metadata = {
            "question": str(question)[:500],  # Limit length
            "query_type": str(intent.query_type if intent else "general"),
            "sources_used": str(",".join(metadata.get("sources", []))),
            "records_count": int(metadata.get("records_fetched", 0)),
        }
        
        print(f"[VECTOR_STORE] Attempting to store Q&A pair...")
        print(f"[VECTOR_STORE] Document length: {len(doc_text)} chars")
        
        # Add to vector store (Pinecone embeds automatically!)
        add_texts(
            texts=[doc_text],
            metadatas=[doc_metadata]
        )
        
        print(f"[VECTOR_STORE] ✓ Successfully stored Q&A pair")
        
    except Exception as e:
        import traceback
        print(f"[VECTOR_STORE] ✗ Storage failed: {e}")
        print(f"[VECTOR_STORE] Traceback: {traceback.format_exc()}")
