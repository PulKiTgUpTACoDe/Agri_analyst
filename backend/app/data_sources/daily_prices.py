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

    def _build_mapped(f: Optional[dict]) -> dict:
        mapped: dict = {}
        if f:
            if f.get("state_keyword") is not None:
                # Try 'state' field (most common in daily prices API)
                mapped["state"] = f["state_keyword"]
            for k in ("district", "market", "commodity", "variety", "grade"):
                if f.get(k) is not None:
                    mapped[k] = f[k]
            for k, v in f.items():
                if isinstance(k, str) and k.startswith("filters[") and v is not None:
                    mapped[k] = v
        return mapped

    async def _call(mapped: dict) -> list[dict]:
        p = params.copy()
        p.update(build_filters_params(mapped))
        print(f"[DAILY_PRICES] Calling API with filters: {mapped}")
        data = await get_json_async(ENDPOINT, p, timeout=timeout)
        records = data.get("records", [])
        print(f"[DAILY_PRICES] Got {len(records)} records")
        return records

    mapped = _build_mapped(filters)
    records = await _call(mapped)
    if records:
        return records

    # Progressive relaxation: only if we have filters and got no results
    if mapped and any(v for v in mapped.values()):
        relax_order = [
            # Keep commodity + state (most important)
            {k: v for k, v in mapped.items() if k in ("commodity", "state")},
            # Keep only state
            {k: v for k, v in mapped.items() if k == "state"},
            # Keep only commodity (last resort)
            {k: v for k, v in mapped.items() if k == "commodity"},
        ]
        seen = set()
        for variant in relax_order:
            key = tuple(sorted(variant.items()))
            if key in seen:
                continue
            seen.add(key)
            if not variant:
                continue
            records = await _call(variant)
            if records:
                return records

    # Don't fetch unfiltered data - return empty if no matches found
    print("[DAILY_PRICES] No records found with any filter combination")
    return []
