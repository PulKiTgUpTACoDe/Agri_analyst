from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

ENDPOINT = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"


async def fetch_daily_prices(
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

    # Map friendly keys to exact dataset field keys where needed
    mapped: dict = {}
    if filters:
        # state.keyword special key mapping
        if "state_keyword" in filters and filters["state_keyword"] is not None:
            mapped["state.keyword"] = filters["state_keyword"]
        # pass-through other known keys
        for k in ("district", "market", "commodity", "variety", "grade"):
            if k in filters and filters[k] is not None:
                mapped[k] = filters[k]
        # allow already-shaped filters[...] keys too
        for k, v in filters.items():
            if isinstance(k, str) and k.startswith("filters["):
                mapped[k] = v

    params.update(build_filters_params(mapped))
    data = await get_json_async(ENDPOINT, params, timeout=timeout)
    return data.get("records", [])
