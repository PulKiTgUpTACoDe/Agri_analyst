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

    def _build_mapped(f: Optional[dict]) -> dict:
        mapped: dict = {}
        if f:
            for k in ("State", "District", "Commodity", "Arrival_Date"):
                if f.get(k) is not None:
                    mapped[k] = f[k]
            # pass-through already-shaped filters[...] keys
            for k, v in f.items():
                if isinstance(k, str) and k.startswith("filters[") and v is not None:
                    mapped[k] = v
        return mapped

    async def _call(mapped: dict, log_prefix: str = "") -> list[dict]:
        p = params.copy()
        p.update(build_filters_params(mapped))
        if log_prefix:
            print(f"[VARIETY_PRICES] {log_prefix} with filters: {mapped}")
        data = await get_json_async(ENDPOINT, p, timeout=timeout)
        records = data.get("records", [])
        if log_prefix:
            print(f"[VARIETY_PRICES] Got {len(records)} records")
        return records

    # Support Arrival_Date list aggregation if provided
    if filters and isinstance(filters.get("Arrival_Date_list"), list):
        all_records: list[dict] = []
        for date_str in filters["Arrival_Date_list"]:
            mapped = _build_mapped({**filters, "Arrival_Date": date_str})
            recs = await _call(mapped)
            if recs:
                all_records.extend(recs)
            if len(all_records) >= limit:
                break
        return all_records[:limit]

    # Attempt with full filters
    mapped = _build_mapped(filters)
    records = await _call(mapped, "Calling API")
    if records:
        return records

    # Progressive relaxation: keep most relevant filters
    if mapped and any(v for v in mapped.values()):
        relax_order = [
            # Keep commodity + state (most important)
            {k: v for k, v in mapped.items() if k in ("Commodity", "State")},
            # Keep only commodity
            {k: v for k, v in mapped.items() if k == "Commodity"},
            # Keep only state
            {k: v for k, v in mapped.items() if k == "State"},
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
    print("[VARIETY_PRICES] No records found with any filter combination")
    return []
