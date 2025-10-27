import json
import asyncio
from operator import itemgetter
from typing import Any
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

from chains.param_extractor import (
    make_param_extractor,
    DailyPricesParams,
    VarietyPricesParams,
    TemperatureSeriesParams,
    RainfallSubdivisionsParams,
)
from data_sources.daily_prices import fetch_daily_prices
from data_sources.variety_prices import fetch_variety_prices
from data_sources.temperature_series import fetch_temperature_series
from data_sources.rainfall_subdivisions import fetch_rainfall_subdivisions


def _format_context(payload: dict[str, list[dict]], max_per_source: int = 10) -> str:
    trimmed = {k: v[:max_per_source] for k, v in payload.items()}
    return json.dumps(trimmed, ensure_ascii=False)


async def _fetch_all(params_bundle: dict[str, Any]) -> dict[str, list[dict]]:
    dp_params = params_bundle.get("daily_prices", {})
    vp_params = params_bundle.get("variety_prices", {})
    ts_params = params_bundle.get("temperature_series", {})
    rf_params = params_bundle.get("rainfall_subdivisions", {})

    results = await asyncio.gather(
        fetch_daily_prices(dp_params, limit=dp_params.get("limit", 50)),
        fetch_variety_prices(vp_params, limit=vp_params.get("limit", 50)),
        fetch_temperature_series(ts_params, limit=ts_params.get("limit", 50)),
        fetch_rainfall_subdivisions(rf_params, limit=rf_params.get("limit", 50)),
        return_exceptions=True,
    )

    def _ok(x):
        return x if isinstance(x, list) else []

    return {
        "daily_prices": _ok(results[0]),
        "variety_prices": _ok(results[1]),
        "temperature_series": _ok(results[2]),
        "rainfall_subdivisions": _ok(results[3]),
    }


def build_pipeline():
    # 1) Build per-endpoint param extractors (deterministic, no agent)
    extract_dp = make_param_extractor(DailyPricesParams)
    extract_vp = make_param_extractor(VarietyPricesParams)
    extract_ts = make_param_extractor(TemperatureSeriesParams)
    extract_rf = make_param_extractor(RainfallSubdivisionsParams)

    def extract_then_fetch(inp: dict[str, str]) -> str:
        # Extract params via LLM
        dp = extract_dp.invoke({"question": inp["question"]})
        vp = extract_vp.invoke({"question": inp["question"]})
        ts = extract_ts.invoke({"question": inp["question"]})
        rf = extract_rf.invoke({"question": inp["question"]})

        # Convert to dicts for fetchers
        params_bundle = {
            "daily_prices": dp.model_dump(),
            "variety_prices": vp.model_dump(),
            "temperature_series": ts.model_dump(),
            "rainfall_subdivisions": rf.model_dump(),
        }
        # Run async fetches concurrently
        payload = asyncio.run(_fetch_all(params_bundle))
        return _format_context(payload, max_per_source=5)

    inputs = {
        "question": itemgetter("question"),
        "context": RunnableLambda(lambda x: extract_then_fetch(x)),
    }

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

    return inputs | prompt | model | StrOutputParser()
