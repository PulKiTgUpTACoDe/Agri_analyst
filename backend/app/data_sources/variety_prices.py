from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

ENDPOINT = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"


async def fetch_variety_prices(
    filters: Optional[dict],
    *,
    limit: int = 50,
    offset: int = 0,
    timeout: int = 30,
) -> list[dict]:
    api_key = get_api_key()
    if not api_key:
        return []

    params = {
        "api-key": api_key,
        "format": "json",
        "limit": str(limit),
        "offset": str(offset),
    }

    mapped: dict = {}
    if filters:
        for k in ("State", "District", "Commodity", "Arrival_Date"):
            if k in filters and filters[k] is not None:
                mapped[k] = filters[k]
        for k, v in filters.items():
            if isinstance(k, str) and k.startswith("filters["):
                mapped[k] = v

    params.update(build_filters_params(mapped))
    data = await get_json_async(ENDPOINT, params, timeout=timeout)
    return data.get("records", [])
