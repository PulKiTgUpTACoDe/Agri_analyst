from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

ENDPOINT = "https://api.data.gov.in/resource/08d46edd-f960-43b9-912b-271e22836976"


async def fetch_temperature_series(
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
        for k in ("document_id", "year", "_annual", "_jan_feb", "_mar_may", "_jun_sep", "_oct_dec"):
            if k in filters and filters[k] is not None:
                mapped[k] = filters[k]
        for k, v in filters.items():
            if isinstance(k, str) and k.startswith("filters["):
                mapped[k] = v

    params.update(build_filters_params(mapped))
    data = await get_json_async(ENDPOINT, params, timeout=timeout)
    return data.get("records", [])
