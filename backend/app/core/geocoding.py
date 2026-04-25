import logging
from typing import Optional

logger = logging.getLogger("agri.geocoding")

INDIAN_STATES: dict[str, tuple[float, float]] = {
    "andhra pradesh": (15.9129, 79.74), "arunachal pradesh": (28.218, 94.7278),
    "assam": (26.2006, 92.9376), "bihar": (25.0961, 85.3131),
    "chhattisgarh": (21.2787, 81.8661), "goa": (15.2993, 74.124),
    "gujarat": (22.2587, 71.1924), "haryana": (29.0588, 76.0856),
    "himachal pradesh": (31.1048, 77.1734), "jharkhand": (23.6102, 85.2799),
    "karnataka": (15.3173, 75.7139), "kerala": (10.8505, 76.2711),
    "madhya pradesh": (22.9734, 78.6569), "maharashtra": (19.7515, 75.7139),
    "manipur": (24.6637, 93.9063), "meghalaya": (25.467, 91.3662),
    "mizoram": (23.1645, 92.9376), "nagaland": (26.1584, 94.5624),
    "odisha": (20.9517, 85.0985), "punjab": (31.1471, 75.3412),
    "rajasthan": (27.0238, 74.2179), "sikkim": (27.533, 88.5122),
    "tamil nadu": (11.1271, 78.6569), "telangana": (18.1124, 79.0193),
    "tripura": (23.9408, 91.9882), "uttar pradesh": (26.8467, 80.9462),
    "uttarakhand": (30.0668, 79.0193), "west bengal": (22.9868, 87.855),
    "andaman and nicobar islands": (11.7401, 92.6586), "chandigarh": (30.7333, 76.7794),
    "dadra and nagar haveli and daman and diu": (20.1809, 73.0169),
    "delhi": (28.7041, 77.1025), "jammu and kashmir": (33.7782, 76.5762),
    "ladakh": (34.1526, 77.5771), "lakshadweep": (10.5667, 72.6417),
    "puducherry": (11.9416, 79.8083),
}

STATE_ALIASES: dict[str, str] = {
    "ap": "andhra pradesh", "ar": "arunachal pradesh", "as": "assam",
    "br": "bihar", "cg": "chhattisgarh", "ga": "goa", "gj": "gujarat",
    "hr": "haryana", "hp": "himachal pradesh", "jh": "jharkhand",
    "ka": "karnataka", "kl": "kerala", "mp": "madhya pradesh",
    "mh": "maharashtra", "mn": "manipur", "ml": "meghalaya", "mz": "mizoram",
    "nl": "nagaland", "or": "odisha", "pb": "punjab", "rj": "rajasthan",
    "sk": "sikkim", "tn": "tamil nadu", "ts": "telangana", "tr": "tripura",
    "up": "uttar pradesh", "uk": "uttarakhand", "wb": "west bengal",
    "dl": "delhi", "jk": "jammu and kashmir",
    "panjab": "punjab", "tamilnadu": "tamil nadu", "utter pradesh": "uttar pradesh",
    "orissa": "odisha", "bengal": "west bengal", "maharastra": "maharashtra",
    "karnatak": "karnataka", "rajastan": "rajasthan", "rajsthan": "rajasthan",
    "gujrat": "gujarat", "chhatisgarh": "chhattisgarh", "chattisgarh": "chhattisgarh",
    "j&k": "jammu and kashmir", "j and k": "jammu and kashmir",
    "new delhi": "delhi", "pondicherry": "puducherry",
    "uttrakhand": "uttarakhand", "uttaranchal": "uttarakhand",
}

MAJOR_DISTRICTS: dict[str, dict[str, tuple[float, float]]] = {
    "punjab": {"ludhiana": (30.901, 75.8573), "amritsar": (31.634, 74.8723), "patiala": (30.3398, 76.3869),
               "jalandhar": (31.326, 75.5762), "bathinda": (30.211, 74.9455), "sangrur": (30.2507, 75.8412)},
    "haryana": {"karnal": (29.6857, 76.9905), "hisar": (29.1492, 75.7217), "ambala": (30.3782, 76.7767),
                "rohtak": (28.8955, 76.6066), "sonipat": (28.9845, 77.0151), "sirsa": (29.5349, 75.0289)},
    "uttar pradesh": {"lucknow": (26.8467, 80.9462), "varanasi": (25.3176, 82.9739), "agra": (27.1767, 78.0081),
                      "meerut": (28.9845, 77.7064), "gorakhpur": (26.7606, 83.3732), "bareilly": (28.367, 79.4304)},
    "maharashtra": {"mumbai": (19.076, 72.8777), "pune": (18.5204, 73.8567), "nagpur": (21.1458, 79.0882),
                    "nashik": (19.9975, 73.7898), "solapur": (17.6599, 75.9064), "kolhapur": (16.705, 74.2433)},
    "madhya pradesh": {"bhopal": (23.2599, 77.4126), "indore": (22.7196, 75.8577), "jabalpur": (23.1815, 79.9864),
                       "gwalior": (26.2183, 78.1828), "ujjain": (23.1765, 75.7885)},
    "rajasthan": {"jaipur": (26.9124, 75.7873), "jodhpur": (26.2389, 73.0243), "udaipur": (24.5854, 73.7125),
                  "kota": (25.2138, 75.8648), "bikaner": (28.0229, 73.3119), "ajmer": (26.4499, 74.6399)},
    "west bengal": {"kolkata": (22.5726, 88.3639), "howrah": (22.5958, 88.2636), "bardhaman": (23.2332, 87.8615),
                    "nadia": (23.471, 88.5565), "murshidabad": (24.1745, 88.2759)},
    "tamil nadu": {"chennai": (13.0827, 80.2707), "coimbatore": (11.0168, 76.9558), "madurai": (9.9252, 78.1198),
                   "salem": (11.6643, 78.146), "thanjavur": (10.787, 79.1378)},
    "karnataka": {"bengaluru": (12.9716, 77.5946), "mysuru": (12.2958, 76.6394), "belgaum": (15.8497, 74.4977),
                  "mangalore": (12.9141, 74.856), "hubli-dharwad": (15.3647, 75.124)},
    "andhra pradesh": {"visakhapatnam": (17.6868, 83.2185), "vijayawada": (16.5062, 80.648),
                       "guntur": (16.3067, 80.4365), "kurnool": (15.8281, 78.0373), "nellore": (14.4426, 79.9865)},
}

def _normalize(name: str) -> str:
    n = name.strip().lower()
    return STATE_ALIASES.get(n, n)

def get_state_coordinates(state_name: str) -> Optional[tuple[float, float]]:
    n = _normalize(state_name)
    if n in INDIAN_STATES:
        return INDIAN_STATES[n]
    for name, coords in INDIAN_STATES.items():
        if n in name or name in n:
            return coords
    return None

def get_district_coordinates(state_name: str, district_name: str) -> Optional[tuple[float, float]]:
    state_n = _normalize(state_name)
    dist_n = district_name.strip().lower()
    districts = MAJOR_DISTRICTS.get(state_n, {})
    if dist_n in districts:
        return districts[dist_n]
    for name, coords in districts.items():
        if dist_n in name or name in dist_n:
            return coords
    return get_state_coordinates(state_name)

def resolve_location(state: Optional[str] = None, district: Optional[str] = None,
                     subdivision: Optional[str] = None) -> Optional[dict]:
    loc = subdivision or state
    if not loc:
        return None
    if district and state:
        coords = get_district_coordinates(state, district)
        if coords:
            return {"latitude": coords[0], "longitude": coords[1], "name": f"{district.title()}, {state.title()}", "level": "district"}
    coords = get_state_coordinates(loc)
    if coords:
        return {"latitude": coords[0], "longitude": coords[1], "name": loc.title(), "level": "state"}
    return None
