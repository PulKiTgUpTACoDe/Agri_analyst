from typing import Optional
from .helpers import build_filters_params, get_api_key, get_json_async

ENDPOINT = "https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de"


async def fetch_crop_production(
    filters: Optional[dict],
    *,
    limit: int = 100,
    offset: int = 0,
    timeout: int = 30,
) -> list[dict]:
    """Fetch district-wise, season-wise crop production statistics.
    
    Filters:
        state_name: State name (e.g., 'Maharashtra', 'Punjab')
        district_name: District name
        crop_year: Crop year (e.g., 2020, 2021)
        season: Season (e.g., 'Kharif', 'Rabi', 'Summer', 'Whole Year')
        crop: Crop name (e.g., 'Rice', 'Wheat', 'Cotton')
        area_: Area in hectares (numeric filter)
        production_: Production in tonnes (numeric filter)
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
            # Map parameter names to API field names
            for k in ("state_name", "district_name", "crop_year", "season", "crop", "area_", "production_"):
                if f.get(k) is not None:
                    mapped[k] = f[k]
            for k, v in f.items():
                if isinstance(k, str) and k.startswith("filters[") and v is not None:
                    mapped[k] = v
        return mapped

    async def _call(mapped: dict, log_prefix: str = "") -> list[dict]:
        p = params.copy()
        p.update(build_filters_params(mapped))
        if log_prefix:
            print(f"[CROP_PRODUCTION] {log_prefix} with filters: {mapped}")
        data = await get_json_async(ENDPOINT, p, timeout=timeout)
        records = data.get("records", [])
        if log_prefix:
            print(f"[CROP_PRODUCTION] Got {len(records)} records")
        return records

    # Attempt with full filters
    mapped = _build_mapped(filters)
    records = await _call(mapped, "Calling API")
    if records:
        return records

    # Progressive relaxation: keep most relevant filters
    if mapped and any(v for v in mapped.values()):
        relax_order = [
            # Keep crop + state (most important for production queries)
            {k: v for k, v in mapped.items() if k in ("crop", "state_name", "crop_year")},
            # Keep only crop + year
            {k: v for k, v in mapped.items() if k in ("crop", "crop_year")},
            # Keep only state + year
            {k: v for k, v in mapped.items() if k in ("state_name", "crop_year")},
            # Keep only crop
            {k: v for k, v in mapped.items() if k == "crop"},
            # Keep only state
            {k: v for k, v in mapped.items() if k == "state_name"},
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

    # Don't fetch unfiltered data - return empty if no matches found
    print("[CROP_PRODUCTION] No records found with any filter combination")
    return []
