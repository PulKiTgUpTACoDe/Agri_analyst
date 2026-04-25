import hashlib, json, logging
from dataclasses import dataclass
from typing import Any, Optional
from cachetools import TTLCache

logger = logging.getLogger("agri.cache")

DEFAULT_TTLS = {
    "daily_prices": 900, "variety_prices": 900, "crop_production": 21600,
    "weather_current": 1800, "weather_forecast": 3600, "weather_historical": 86400, "default": 3600,
}

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total * 100, 1) if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "hit_rate_percent": self.hit_rate,
                "sets": self.sets, "current_size": self.current_size, "max_size": self.max_size}

class CacheManager:
    def __init__(self, max_size: int = 500, default_ttl: int = 3600):
        self._stats = CacheStats(max_size=max_size)
        self._default_ttl = default_ttl
        self._caches: dict[str, TTLCache] = {}

    def _get_cache(self, category: str) -> TTLCache:
        if category not in self._caches:
            self._caches[category] = TTLCache(maxsize=100, ttl=DEFAULT_TTLS.get(category, self._default_ttl))
        return self._caches[category]

    def get(self, key: str, category: str = "default") -> Optional[Any]:
        val = self._get_cache(category).get(key)
        if val is not None:
            self._stats.hits += 1
            return val
        self._stats.misses += 1
        return None

    def set(self, key: str, value: Any, category: str = "default") -> None:
        self._get_cache(category)[key] = value
        self._stats.sets += 1
        self._stats.current_size = sum(len(c) for c in self._caches.values())

    def invalidate(self, category: Optional[str] = None) -> int:
        if category and category in self._caches:
            count = len(self._caches[category])
            self._caches[category].clear()
            return count
        total = sum(len(c) for c in self._caches.values())
        for c in self._caches.values():
            c.clear()
        return total

    @property
    def stats(self) -> CacheStats:
        self._stats.current_size = sum(len(c) for c in self._caches.values())
        return self._stats

    @staticmethod
    def make_key(prefix: str, params: dict) -> str:
        raw = json.dumps({"p": prefix, **params}, sort_keys=True)
        return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

_cache: Optional[CacheManager] = None

def get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache
