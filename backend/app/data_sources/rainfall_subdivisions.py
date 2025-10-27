from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

ENDPOINT = "https://api.data.gov.in/resource/8e0bd482-4aba-4d99-9cb9-ff124f6f1c2f"


async def fetch_rainfall_subdivisions(
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

    # Currently docs list no field filters; pass-through if provided
    mapped: dict = {}
    if filters:
        for k, v in filters.items():
            if v is not None and k != 'limit':
                mapped[k] = v

    params.update(build_filters_params(mapped))
    print(f"[RAINFALL] Calling API with filters: {mapped}")
    data = await get_json_async(ENDPOINT, params, timeout=timeout)
    records = data.get("records", [])
    print(f"[RAINFALL] Got {len(records)} records")
    
    # If no records found with filters, return empty (don't fetch unfiltered)
    if not records and mapped:
        print("[RAINFALL] No records found with filters")
        return []
    
    return records
