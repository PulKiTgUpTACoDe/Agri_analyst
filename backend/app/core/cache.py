"""TTL-based in-memory cache for API responses.

Uses cachetools.TTLCache with configurable TTL per data type.
Designed for serverless (Vercel) – cache lives per-instance.
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger("agri.cache")

# ── Default TTLs (seconds) ────────────────────────────────────────────────────

DEFAULT_TTLS = {
    "daily_prices": 900,       # 15 min – changes frequently
    "variety_prices": 900,     # 15 min
    "crop_production": 21600,  # 6 hours – updated infrequently
    "weather_current": 1800,   # 30 min
    "weather_forecast": 3600,  # 1 hour
    "weather_historical": 86400,  # 24 hours – doesn't change
    "default": 3600,           # 1 hour fallback
}

# ── Cache stats ───────────────────────────────────────────────────────────────


@dataclass
class CacheStats:
    """Cache performance metrics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total * 100, 1) if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": self.hit_rate,
            "sets": self.sets,
            "current_size": self.current_size,
            "max_size": self.max_size,
        }


# ── Cache manager ─────────────────────────────────────────────────────────────


class CacheManager:
    """TTL-based in-memory cache with per-category TTLs."""

    def __init__(self, max_size: int = 500, default_ttl: int = 3600):
        """Initialize cache.

        Args:
            max_size: Maximum number of cached items.
            default_ttl: Default TTL in seconds.
        """
        self._cache = TTLCache(maxsize=max_size, ttl=default_ttl)
        self._stats = CacheStats(max_size=max_size)
        self._default_ttl = default_ttl
        # Separate caches per TTL category for accurate expiry
        self._category_caches: dict[str, TTLCache] = {}

    def _get_category_cache(self, category: str) -> TTLCache:
        """Get or create a TTL cache for a specific category."""
        if category not in self._category_caches:
            ttl = DEFAULT_TTLS.get(category, self._default_ttl)
            self._category_caches[category] = TTLCache(
                maxsize=100, ttl=ttl
            )
        return self._category_caches[category]

    def get(self, key: str, category: str = "default") -> Optional[Any]:
        """Get a value from cache.

        Args:
            key: Cache key.
            category: Data category for TTL selection.

        Returns:
            Cached value or None.
        """
        cache = self._get_category_cache(category)
        value = cache.get(key)
        if value is not None:
            self._stats.hits += 1
            logger.debug("Cache HIT [%s]: %s", category, key[:20])
            return value
        self._stats.misses += 1
        return None

    def set(self, key: str, value: Any, category: str = "default") -> None:
        """Store a value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            category: Data category for TTL selection.
        """
        cache = self._get_category_cache(category)
        cache[key] = value
        self._stats.sets += 1
        self._stats.current_size = sum(len(c) for c in self._category_caches.values())
        logger.debug("Cache SET [%s]: %s", category, key[:20])

    def invalidate(self, category: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            category: If provided, clear only that category. Otherwise clear all.

        Returns:
            Number of entries removed.
        """
        if category and category in self._category_caches:
            count = len(self._category_caches[category])
            self._category_caches[category].clear()
            logger.info("Invalidated %d entries in category '%s'", count, category)
            return count

        total = sum(len(c) for c in self._category_caches.values())
        for c in self._category_caches.values():
            c.clear()
        logger.info("Invalidated all %d cache entries", total)
        return total

    @property
    def stats(self) -> CacheStats:
        """Get current cache stats."""
        self._stats.current_size = sum(len(c) for c in self._category_caches.values())
        return self._stats

    @staticmethod
    def make_key(prefix: str, params: dict) -> str:
        """Generate a deterministic cache key from parameters."""
        raw = json.dumps({"p": prefix, **params}, sort_keys=True)
        return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# ── Singleton ─────────────────────────────────────────────────────────────────

_cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get or create the global CacheManager instance."""
    global _cache
    if _cache is None:
        _cache = CacheManager(max_size=500, default_ttl=3600)
    return _cache
