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
)
from app.data_sources.daily_prices import fetch_daily_prices
from app.data_sources.variety_prices import fetch_variety_prices
from app.data_sources.temperature_series import fetch_temperature_series
from app.data_sources.rainfall_subdivisions import fetch_rainfall_subdivisions


def _format_context(payload: dict[str, list[dict]], max_per_source: int = 10) -> str:
    trimmed = {k: v[:max_per_source] for k, v in payload.items()}
    return json.dumps(trimmed, ensure_ascii=False)


async def _fetch_all(params_bundle: dict[str, Any]) -> dict[str, list[dict]]:
    dp_params = params_bundle.get("daily_prices", {})
    vp_params = params_bundle.get("variety_prices", {})
    ts_params = params_bundle.get("temperature_series", {})
    rf_params = params_bundle.get("rainfall_subdivisions", {})

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
    
    # If no meaningful params for any endpoint, fetch from daily_prices with limit
    if not tasks:
        print("[DEBUG] No specific params found, fetching sample from daily_prices")
        tasks.append(fetch_daily_prices({}, limit=10))
        task_names.append("daily_prices")
    
    results = await asyncio.gather(*tasks, return_exceptions=True)

    def _ok(x):
        return x if isinstance(x, list) else []

    # Map results back to endpoint names
    result_map = {"daily_prices": [], "variety_prices": [], "temperature_series": [], "rainfall_subdivisions": []}
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

    dp = await extract_dp.ainvoke({"question": question})
    vp = await extract_vp.ainvoke({"question": question})
    ts = await extract_ts.ainvoke({"question": question})
    rf = await extract_rf.ainvoke({"question": question})

    params_bundle = {
        "daily_prices": dp.model_dump(),
        "variety_prices": vp.model_dump(),
        "temperature_series": ts.model_dump(),
        "rainfall_subdivisions": rf.model_dump(),
    }

    payload = await _fetch_all(params_bundle)
    context = _format_context(payload, max_per_source=5)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are Agriculture Analyst. Use the provided API context when answering. Be concise and cite numbers when relevant."),
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
