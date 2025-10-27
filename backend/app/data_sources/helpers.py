import os
from typing import Any, Dict
import httpx    


def build_filters_params(filters: Dict[str, Any] | None) -> Dict[str, str]:
    """Convert a simple dict into data.gov.in filters[...] query params.
    If a key already starts with "filters[", it is passed through.
    """
    if not filters:
        return {}
    out: Dict[str, str] = {}
    for k, v in filters.items():
        if v is None:
            continue
        key = k if k.startswith("filters[") else f"filters[{k}]"
        out[key] = str(v)
    return out


def get_api_key() -> str | None:
    return os.getenv("GOV_API_KEY")


async def get_json_async(url: str, params: Dict[str, str], timeout: int = 30) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        print(f"[API_CALL] URL: {url}")
        print(f"[API_CALL] Params: {params}")
        r = await client.get(url, params=params)
        print(f"[API_CALL] Status: {r.status_code}")
        print(f"[API_CALL] Response URL: {r.url}")
        r.raise_for_status()
        result = r.json() or {}
        print(f"[API_CALL] Records returned: {len(result.get('records', []))}")
        return result
