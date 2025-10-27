from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

# Note: Using same endpoint as crop production based on user info
# If there's a separate rainfall endpoint, update this URL
ENDPOINT = "https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de"


async def fetch_district_rainfall(
    filters: Optional[dict],
    *,
    limit: int = 100,
    offset: int = 0,
    timeout: int = 30,
) -> list[dict]:
    """Fetch state-wise/district-wise rainfall data.
    
    Filters:
        state_name: State name (e.g., 'Maharashtra', 'Karnataka')
        district_name: District name
        year: Year (numeric)
        month: Month (if available)
        subdivision: Subdivision name (if available)
    
    Note: The exact fields depend on the actual rainfall dataset structure.
    Update this based on actual API response.
    """
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
            # Map parameter names - adjust based on actual rainfall API fields
            for k in ("state_name", "district_name", "year", "month", "subdivision"):
                if f.get(k) is not None:
                    mapped[k] = f[k]
            # Pass-through already-shaped filters[...] keys
            for k, v in f.items():
                if isinstance(k, str) and k.startswith("filters[") and v is not None:
                    mapped[k] = v
        return mapped

    async def _call(mapped: dict, log_prefix: str = "") -> list[dict]:
        p = params.copy()
        p.update(build_filters_params(mapped))
        if log_prefix:
            print(f"[DISTRICT_RAINFALL] {log_prefix} with filters: {mapped}")
        data = await get_json_async(ENDPOINT, p, timeout=timeout)
        records = data.get("records", [])
        if log_prefix:
            print(f"[DISTRICT_RAINFALL] Got {len(records)} records")
        return records

    # Attempt with full filters
    mapped = _build_mapped(filters)
    records = await _call(mapped, "Calling API")
    if records:
        return records

    # Progressive relaxation
    if mapped and any(v for v in mapped.values()):
        relax_order = [
            # Keep state + year
            {k: v for k, v in mapped.items() if k in ("state_name", "year")},
            # Keep only state
            {k: v for k, v in mapped.items() if k == "state_name"},
            # Keep only year
            {k: v for k, v in mapped.items() if k == "year"},
        ]
        seen = set()
        for variant in relax_order:
            key = tuple(sorted(variant.items()))
            if key in seen:
                continue
            seen.add(key)
            if not variant:
                continue
            records = await _call(variant, "Relaxed attempt")
            if records:
                return records

    # Don't fetch unfiltered data
    print("[DISTRICT_RAINFALL] No records found with any filter combination")
    return []
