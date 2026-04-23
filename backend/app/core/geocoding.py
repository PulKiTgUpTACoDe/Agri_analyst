"""Indian state/district to lat/lon geocoding lookup.

Bundled data – no external API calls needed. Supports fuzzy matching
for misspellings (e.g., 'Panjab' -> 'Punjab').
"""
import logging
from typing import Optional

logger = logging.getLogger("agri.geocoding")

# ── State centroids (lat, lon) ────────────────────────────────────────────────
# Approximate geographic centers for all 36 Indian states/UTs.

INDIAN_STATES: dict[str, tuple[float, float]] = {
    "andhra pradesh": (15.9129, 79.7400),
    "arunachal pradesh": (28.2180, 94.7278),
    "assam": (26.2006, 92.9376),
    "bihar": (25.0961, 85.3131),
    "chhattisgarh": (21.2787, 81.8661),
    "goa": (15.2993, 74.1240),
    "gujarat": (22.2587, 71.1924),
    "haryana": (29.0588, 76.0856),
    "himachal pradesh": (31.1048, 77.1734),
    "jharkhand": (23.6102, 85.2799),
    "karnataka": (15.3173, 75.7139),
    "kerala": (10.8505, 76.2711),
    "madhya pradesh": (22.9734, 78.6569),
    "maharashtra": (19.7515, 75.7139),
    "manipur": (24.6637, 93.9063),
    "meghalaya": (25.4670, 91.3662),
    "mizoram": (23.1645, 92.9376),
    "nagaland": (26.1584, 94.5624),
    "odisha": (20.9517, 85.0985),
    "punjab": (31.1471, 75.3412),
    "rajasthan": (27.0238, 74.2179),
    "sikkim": (27.5330, 88.5122),
    "tamil nadu": (11.1271, 78.6569),
    "telangana": (18.1124, 79.0193),
    "tripura": (23.9408, 91.9882),
    "uttar pradesh": (26.8467, 80.9462),
    "uttarakhand": (30.0668, 79.0193),
    "west bengal": (22.9868, 87.8550),
    # Union Territories
    "andaman and nicobar islands": (11.7401, 92.6586),
    "chandigarh": (30.7333, 76.7794),
    "dadra and nagar haveli and daman and diu": (20.1809, 73.0169),
    "delhi": (28.7041, 77.1025),
    "jammu and kashmir": (33.7782, 76.5762),
    "ladakh": (34.1526, 77.5771),
    "lakshadweep": (10.5667, 72.6417),
    "puducherry": (11.9416, 79.8083),
}

# ── Common aliases ────────────────────────────────────────────────────────────

STATE_ALIASES: dict[str, str] = {
    "ap": "andhra pradesh",
    "ar": "arunachal pradesh",
    "as": "assam",
    "br": "bihar",
    "cg": "chhattisgarh",
    "ga": "goa",
    "gj": "gujarat",
    "hr": "haryana",
    "hp": "himachal pradesh",
    "jh": "jharkhand",
    "ka": "karnataka",
    "kl": "kerala",
    "mp": "madhya pradesh",
    "mh": "maharashtra",
    "mn": "manipur",
    "ml": "meghalaya",
    "mz": "mizoram",
    "nl": "nagaland",
    "or": "odisha",
    "pb": "punjab",
    "rj": "rajasthan",
    "sk": "sikkim",
    "tn": "tamil nadu",
    "ts": "telangana",
    "tr": "tripura",
    "up": "uttar pradesh",
    "uk": "uttarakhand",
    "wb": "west bengal",
    "dl": "delhi",
    "jk": "jammu and kashmir",
    # Common misspellings
    "panjab": "punjab",
    "tamilnadu": "tamil nadu",
    "utter pradesh": "uttar pradesh",
    "uttar pradesh": "uttar pradesh",
    "orissa": "odisha",
    "bengal": "west bengal",
    "maharastra": "maharashtra",
    "karnatak": "karnataka",
    "rajastan": "rajasthan",
    "rajsthan": "rajasthan",
    "gujrat": "gujarat",
    "chhatisgarh": "chhattisgarh",
    "chattisgarh": "chhattisgarh",
    "j&k": "jammu and kashmir",
    "j and k": "jammu and kashmir",
    "new delhi": "delhi",
    "pondicherry": "puducherry",
    "uttrakhand": "uttarakhand",
    "uttaranchal": "uttarakhand",
}

# ── Major district centroids (top agricultural districts) ─────────────────────
# A selection of major agricultural districts with their coordinates.

MAJOR_DISTRICTS: dict[str, dict[str, tuple[float, float]]] = {
    "punjab": {
        "ludhiana": (30.9010, 75.8573),
        "amritsar": (31.6340, 74.8723),
        "patiala": (30.3398, 76.3869),
        "jalandhar": (31.3260, 75.5762),
        "bathinda": (30.2110, 74.9455),
        "sangrur": (30.2507, 75.8412),
        "moga": (30.8185, 75.1741),
        "firozpur": (30.9331, 74.6225),
        "gurdaspur": (32.0414, 75.4028),
        "hoshiarpur": (31.5143, 75.9115),
    },
    "haryana": {
        "karnal": (29.6857, 76.9905),
        "hisar": (29.1492, 75.7217),
        "ambala": (30.3782, 76.7767),
        "rohtak": (28.8955, 76.6066),
        "sonipat": (28.9845, 77.0151),
        "panipat": (29.3909, 76.9635),
        "sirsa": (29.5349, 75.0289),
        "jind": (29.3159, 76.3143),
        "kaithal": (29.8015, 76.3998),
        "kurukshetra": (29.9695, 76.8783),
    },
    "uttar pradesh": {
        "lucknow": (26.8467, 80.9462),
        "varanasi": (25.3176, 82.9739),
        "agra": (27.1767, 78.0081),
        "allahabad": (25.4358, 81.8463),
        "meerut": (28.9845, 77.7064),
        "gorakhpur": (26.7606, 83.3732),
        "bareilly": (28.3670, 79.4304),
        "moradabad": (28.8386, 78.7733),
        "aligarh": (27.8974, 78.0880),
        "muzaffarnagar": (29.4727, 77.7085),
    },
    "maharashtra": {
        "mumbai": (19.0760, 72.8777),
        "pune": (18.5204, 73.8567),
        "nagpur": (21.1458, 79.0882),
        "nashik": (19.9975, 73.7898),
        "aurangabad": (19.8762, 75.3433),
        "solapur": (17.6599, 75.9064),
        "kolhapur": (16.7050, 74.2433),
        "ahmednagar": (19.0948, 74.7480),
        "sangli": (16.8524, 74.5815),
        "satara": (17.6805, 74.0183),
    },
    "madhya pradesh": {
        "bhopal": (23.2599, 77.4126),
        "indore": (22.7196, 75.8577),
        "jabalpur": (23.1815, 79.9864),
        "gwalior": (26.2183, 78.1828),
        "ujjain": (23.1765, 75.7885),
        "sagar": (23.8388, 78.7378),
        "dewas": (22.9623, 76.0508),
        "ratlam": (23.3263, 75.0488),
        "hoshangabad": (22.7475, 77.7285),
        "vidisha": (23.5239, 77.8081),
    },
    "rajasthan": {
        "jaipur": (26.9124, 75.7873),
        "jodhpur": (26.2389, 73.0243),
        "udaipur": (24.5854, 73.7125),
        "kota": (25.2138, 75.8648),
        "bikaner": (28.0229, 73.3119),
        "ajmer": (26.4499, 74.6399),
        "alwar": (27.5529, 76.6346),
        "bharatpur": (27.2152, 77.5030),
        "sikar": (27.6094, 75.1398),
        "sri ganganagar": (29.9038, 73.8772),
    },
    "west bengal": {
        "kolkata": (22.5726, 88.3639),
        "howrah": (22.5958, 88.2636),
        "bardhaman": (23.2332, 87.8615),
        "nadia": (23.4710, 88.5565),
        "murshidabad": (24.1745, 88.2759),
        "hooghly": (22.9086, 88.3967),
        "north 24 parganas": (22.6168, 88.4298),
        "south 24 parganas": (22.1352, 88.4015),
        "midnapore": (22.4256, 87.3197),
        "birbhum": (23.8597, 87.5528),
    },
    "tamil nadu": {
        "chennai": (13.0827, 80.2707),
        "coimbatore": (11.0168, 76.9558),
        "madurai": (9.9252, 78.1198),
        "tiruchirappalli": (10.7905, 78.7047),
        "salem": (11.6643, 78.1460),
        "tirunelveli": (8.7139, 77.7567),
        "erode": (11.3410, 77.7172),
        "thanjavur": (10.7870, 79.1378),
        "vellore": (12.9165, 79.1325),
        "dindigul": (10.3673, 77.9803),
    },
    "karnataka": {
        "bengaluru": (12.9716, 77.5946),
        "mysuru": (12.2958, 76.6394),
        "belgaum": (15.8497, 74.4977),
        "gulbarga": (17.3297, 76.8343),
        "hubli-dharwad": (15.3647, 75.1240),
        "mangalore": (12.9141, 74.8560),
        "bellary": (15.1394, 76.9214),
        "shimoga": (13.9299, 75.5681),
        "tumkur": (13.3379, 77.1173),
        "raichur": (16.2076, 77.3463),
    },
    "andhra pradesh": {
        "visakhapatnam": (17.6868, 83.2185),
        "vijayawada": (16.5062, 80.6480),
        "guntur": (16.3067, 80.4365),
        "kurnool": (15.8281, 78.0373),
        "nellore": (14.4426, 79.9865),
        "anantapur": (14.6819, 77.6006),
        "tirupati": (13.6288, 79.4192),
        "kakinada": (16.9891, 82.2475),
        "eluru": (16.7107, 81.0952),
        "chittoor": (13.2172, 79.1003),
    },
}


def get_state_coordinates(state_name: str) -> Optional[tuple[float, float]]:
    """Get lat/lon for an Indian state.

    Supports fuzzy matching via aliases for common misspellings.

    Returns:
        (latitude, longitude) or None if not found.
    """
    normalized = state_name.strip().lower()

    # Direct match
    if normalized in INDIAN_STATES:
        return INDIAN_STATES[normalized]

    # Alias match
    if normalized in STATE_ALIASES:
        canonical = STATE_ALIASES[normalized]
        return INDIAN_STATES.get(canonical)

    # Substring match (e.g., "pradesh" in query)
    for name, coords in INDIAN_STATES.items():
        if normalized in name or name in normalized:
            return coords

    logger.warning("State not found: %s", state_name)
    return None


def get_district_coordinates(
    state_name: str, district_name: str
) -> Optional[tuple[float, float]]:
    """Get lat/lon for an Indian district.

    Falls back to state centroid if district not in the database.
    """
    state_norm = state_name.strip().lower()
    district_norm = district_name.strip().lower()

    # Resolve state alias
    if state_norm in STATE_ALIASES:
        state_norm = STATE_ALIASES[state_norm]

    # Look up district
    state_districts = MAJOR_DISTRICTS.get(state_norm, {})
    if district_norm in state_districts:
        return state_districts[district_norm]

    # Substring match for district
    for name, coords in state_districts.items():
        if district_norm in name or name in district_norm:
            return coords

    # Fallback to state centroid
    logger.info("District '%s' not found, falling back to state centroid for '%s'", district_name, state_name)
    return get_state_coordinates(state_name)


def resolve_location(
    state: Optional[str] = None,
    district: Optional[str] = None,
    subdivision: Optional[str] = None,
) -> Optional[dict]:
    """Resolve a location to lat/lon with metadata.

    Args:
        state: State name (preferred).
        district: District name (requires state).
        subdivision: Rainfall subdivision name (treated as state).

    Returns:
        Dict with lat, lon, name, level or None.
    """
    # Try subdivision as state
    location_name = subdivision or state
    if not location_name:
        return None

    if district and state:
        coords = get_district_coordinates(state, district)
        if coords:
            return {
                "latitude": coords[0],
                "longitude": coords[1],
                "name": f"{district.title()}, {state.title()}",
                "level": "district",
            }

    coords = get_state_coordinates(location_name)
    if coords:
        return {
            "latitude": coords[0],
            "longitude": coords[1],
            "name": location_name.title(),
            "level": "state",
        }

    return None
