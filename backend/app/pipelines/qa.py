import json
import asyncio
from typing import Any
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

from app.chains.param_extractor import (
    make_param_extractor,
    DailyPricesParams,
    VarietyPricesParams,
    TemperatureSeriesParams,
    RainfallSubdivisionsParams,
    CropProductionParams,
    DistrictRainfallParams,
)
from app.data_sources.daily_prices import fetch_daily_prices
from app.data_sources.variety_prices import fetch_variety_prices
from app.data_sources.temperature_series import fetch_temperature_series
from app.data_sources.rainfall_subdivisions import fetch_rainfall_subdivisions
from app.data_sources.crop_production import fetch_crop_production
from app.data_sources.district_rainfall import fetch_district_rainfall
from app.pipelines.advanced_qa import run_advanced_pipeline, detect_query_type


def _format_context(payload: dict[str, list[dict]], max_per_source: int = 10) -> str:
    trimmed = {k: v[:max_per_source] for k, v in payload.items()}
    return json.dumps(trimmed, ensure_ascii=False)


async def _fetch_all(params_bundle: dict[str, Any]) -> dict[str, list[dict]]:
    dp_params = params_bundle.get("daily_prices", {})
    vp_params = params_bundle.get("variety_prices", {})
    ts_params = params_bundle.get("temperature_series", {})
    rf_params = params_bundle.get("rainfall_subdivisions", {})
    cp_params = params_bundle.get("crop_production", {})
    dr_params = params_bundle.get("district_rainfall", {})

    # Helper to check if params have meaningful filters (not just limit)
    def has_filters(params: dict) -> bool:
        return any(v is not None and k != 'limit' for k, v in params.items())

    # Only fetch from endpoints that have relevant parameters
    tasks = []
    task_names = []
    
    if has_filters(dp_params):
        tasks.append(fetch_daily_prices(dp_params, limit=dp_params.get("limit", 50)))
        task_names.append("daily_prices")
    
    if has_filters(vp_params):
        tasks.append(fetch_variety_prices(vp_params, limit=vp_params.get("limit", 50)))
        task_names.append("variety_prices")
    
    if has_filters(ts_params):
        tasks.append(fetch_temperature_series(ts_params, limit=ts_params.get("limit", 50)))
        task_names.append("temperature_series")
    
    if has_filters(rf_params):
        tasks.append(fetch_rainfall_subdivisions(rf_params, limit=rf_params.get("limit", 50)))
        task_names.append("rainfall_subdivisions")
    
    if has_filters(cp_params):
        tasks.append(fetch_crop_production(cp_params, limit=cp_params.get("limit", 100)))
        task_names.append("crop_production")
    
    if has_filters(dr_params):
        tasks.append(fetch_district_rainfall(dr_params, limit=dr_params.get("limit", 100)))
        task_names.append("district_rainfall")
    
    # If no meaningful params for any endpoint, fetch from daily_prices with limit
    if not tasks:
        print("[DEBUG] No specific params found, fetching sample from daily_prices")
        tasks.append(fetch_daily_prices({}, limit=10))
        task_names.append("daily_prices")
    
    results = await asyncio.gather(*tasks, return_exceptions=True)

    def _ok(x):
        return x if isinstance(x, list) else []

    # Map results back to endpoint names
    result_map = {
        "daily_prices": [],
        "variety_prices": [],
        "temperature_series": [],
        "rainfall_subdivisions": [],
        "crop_production": [],
        "district_rainfall": [],
    }
    for i, name in enumerate(task_names):
        result_map[name] = _ok(results[i])
    
    print(f"[DEBUG] Fetched records: {[(k, len(v)) for k, v in result_map.items() if v]}")
    return result_map

async def run_pipeline_with_metadata(question: str) -> dict:
    """Run the multi-source pipeline (async) and return answer plus metadata.
    Returns keys: answer, context, usedEndpoints, usedParams.
    """

    extract_dp = make_param_extractor(DailyPricesParams)
    extract_vp = make_param_extractor(VarietyPricesParams)
    extract_ts = make_param_extractor(TemperatureSeriesParams)
    extract_rf = make_param_extractor(RainfallSubdivisionsParams)
    extract_cp = make_param_extractor(CropProductionParams)
    extract_dr = make_param_extractor(DistrictRainfallParams)

    dp = await extract_dp.ainvoke({"question": question})
    vp = await extract_vp.ainvoke({"question": question})
    ts = await extract_ts.ainvoke({"question": question})
    rf = await extract_rf.ainvoke({"question": question})
    cp = await extract_cp.ainvoke({"question": question})
    dr = await extract_dr.ainvoke({"question": question})

    params_bundle = {
        "daily_prices": dp.model_dump(),
        "variety_prices": vp.model_dump(),
        "temperature_series": ts.model_dump(),
        "rainfall_subdivisions": rf.model_dump(),
        "crop_production": cp.model_dump(),
        "district_rainfall": dr.model_dump(),
    }

    payload = await _fetch_all(params_bundle)
    
    # Detect if this is an advanced query requiring analysis
    query_type = detect_query_type(question)
    use_advanced = query_type in ['comparison', 'trend', 'correlation', 'policy', 'ranking']
    
    # Use advanced pipeline for complex queries
    if use_advanced and any(len(v) > 0 for v in payload.values()):
        print(f"[PIPELINE] Using advanced analysis for {query_type} query")
        advanced_result = await run_advanced_pipeline(question, payload)
        return {
            "answer": advanced_result['answer'],
            "context": advanced_result.get('context_preview', ''),
            "usedEndpoints": advanced_result['data_sources_used'],
            "usedParams": params_bundle,
            "query_type": advanced_result['query_type'],
            "analysis": advanced_result.get('analysis', {}),
            "total_records": advanced_result.get('total_records_analyzed', 0)
        }
    
    # Use basic pipeline for simple queries
    print(f"[PIPELINE] Using basic pipeline for {query_type} query")
    context = _format_context(payload, max_per_source=5)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an Agriculture Analyst with access to multiple Indian agricultural datasets.

        Available data sources:
        - daily_prices: Daily market prices for commodities (state/district/market level)
        - variety_prices: Variety-wise commodity prices with arrival dates
        - crop_production: District-wise crop production statistics (area in hectares, production in tonnes, by season and year)
        - district_rainfall: State/district-wise rainfall data
        - temperature_series: Annual and seasonal temperature data
        - rainfall_subdivisions: Subdivision-level rainfall statistics

        When answering:
        - Use the provided API context data
        - Cite specific numbers, states, districts, years when relevant
        - If data is missing or insufficient, clearly state what's available
        - For production queries, mention area, production volume, and season if available
        - For comparison queries, present data side-by-side
        - Be concise but comprehensive"""),
        ("human", "Question: {question}\n\nContext:\n{context}")
    ])
    
    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
        max_output_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "1024")),
    )
    chain = {"question": lambda x: x, "context": lambda x: context} | prompt | model | StrOutputParser()
    answer = await chain.ainvoke(question)

    return {
        "answer": answer,
        "context": context,
        "usedEndpoints": list(payload.keys()),
        "usedParams": params_bundle,
    }
