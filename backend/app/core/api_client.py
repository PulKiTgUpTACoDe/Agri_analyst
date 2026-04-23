"""Hardened API client for data.gov.in with retry, caching, and pagination."""
import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.core.config import get_settings

logger = logging.getLogger("agri.api_client")

# ── Response wrapper ──────────────────────────────────────────────────────────

@dataclass
class ApiResponse:
    """Structured response from a data.gov.in API call."""
    records: list[dict] = field(default_factory=list)
    total: int = 0
    source: str = ""
    resource_id: str = ""
    filters_used: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    from_cache: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.records) > 0


# ── Retry-able exceptions ────────────────────────────────────────────────────

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RetryableAPIError(Exception):
    """Raised for transient HTTP errors that should be retried."""
    pass


class PermanentAPIError(Exception):
    """Raised for non-retryable HTTP errors (4xx except 429)."""
    pass


# ── Main client ──────────────────────────────────────────────────────────────

# Correct data.gov.in endpoint (the old /resource/{id} format returns 403)
DATA_GOV_BASE = "https://api.data.gov.in/resource"


class DataGovClient:
    """Resilient API client for data.gov.in with retry + caching."""

    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
        )
        self._cache = None  # Injected later by cache module

    def set_cache(self, cache):
        """Inject cache manager (avoids circular import)."""
        self._cache = cache

    # ── Core fetch (with retry) ───────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(RetryableAPIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _raw_fetch(
        self, resource_id: str, filters: dict[str, Any], limit: int, offset: int
    ) -> dict:
        """Low-level HTTP fetch with retry on transient errors."""
        params: dict[str, str] = {
            "api-key": self.settings.GOV_API_KEY,
            "format": "json",
            "limit": str(limit),
            "offset": str(offset),
        }
        # Add filters in data.gov.in format
        for key, value in filters.items():
            if value is not None:
                params[f"filters[{key}]"] = str(value)

        url = f"{DATA_GOV_BASE}/{resource_id}"

        try:
            response = await self.client.get(url, params=params)

            if response.status_code in RETRYABLE_STATUS:
                logger.warning(
                    "Retryable HTTP %d from %s", response.status_code, resource_id
                )
                raise RetryableAPIError(
                    f"HTTP {response.status_code} from {resource_id}"
                )

            if response.status_code == 403:
                logger.error("403 Forbidden for resource %s – check API key", resource_id)
                raise PermanentAPIError(
                    f"403 Forbidden for {resource_id}. API key may be invalid or expired."
                )

            response.raise_for_status()
            data = response.json()
            return data

        except httpx.TimeoutException as exc:
            logger.warning("Timeout fetching %s: %s", resource_id, exc)
            raise RetryableAPIError(f"Timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in RETRYABLE_STATUS:
                raise RetryableAPIError(str(exc)) from exc
            raise PermanentAPIError(str(exc)) from exc

    # ── Public fetch ──────────────────────────────────────────────────────

    async def fetch(
        self,
        resource_id: str,
        filters: dict[str, Any],
        limit: int = 1000,
        offset: int = 0,
    ) -> ApiResponse:
        """Fetch data from a data.gov.in resource with caching and retry.

        Args:
            resource_id: The data.gov.in resource identifier.
            filters: Key-value filter pairs (None values are excluded).
            limit: Max records per request (API max varies).
            offset: Pagination offset.

        Returns:
            ApiResponse with records, metadata, and error info.
        """
        # Clean filters – remove None/empty values
        clean_filters = {k: v for k, v in filters.items() if v is not None and v != ""}

        # Check cache first
        cache_key = self._cache_key(resource_id, clean_filters, limit, offset)
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache HIT for %s", resource_id)
                cached.from_cache = True
                return cached

        start = time.monotonic()
        try:
            data = await self._raw_fetch(resource_id, clean_filters, limit, offset)
            elapsed = (time.monotonic() - start) * 1000

            records = data.get("records", [])
            total = int(data.get("total", len(records)))

            result = ApiResponse(
                records=records,
                total=total,
                source="data.gov.in",
                resource_id=resource_id,
                filters_used=clean_filters,
                elapsed_ms=round(elapsed, 1),
            )

            logger.info(
                "Fetched %d/%d records from %s in %.0fms",
                len(records), total, resource_id, elapsed,
            )

            # Cache successful responses
            if self._cache and result.ok:
                self._cache.set(cache_key, result)

            return result

        except (RetryableAPIError, PermanentAPIError) as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("API fetch failed for %s: %s", resource_id, exc)
            return ApiResponse(
                source="data.gov.in",
                resource_id=resource_id,
                filters_used=clean_filters,
                elapsed_ms=round(elapsed, 1),
                error=str(exc),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Unexpected error fetching %s: %s", resource_id, exc)
            return ApiResponse(
                source="data.gov.in",
                resource_id=resource_id,
                filters_used=clean_filters,
                elapsed_ms=round(elapsed, 1),
                error=f"Unexpected: {exc}",
            )

    # ── Paginated fetch ───────────────────────────────────────────────────

    async def fetch_all(
        self,
        resource_id: str,
        filters: dict[str, Any],
        max_records: int = 5000,
        page_size: int = 1000,
    ) -> ApiResponse:
        """Fetch all records with automatic pagination."""
        all_records: list[dict] = []
        offset = 0

        while len(all_records) < max_records:
            batch_limit = min(page_size, max_records - len(all_records))
            resp = await self.fetch(resource_id, filters, limit=batch_limit, offset=offset)

            if resp.error or not resp.records:
                if all_records:
                    # Return what we have so far
                    break
                return resp  # Return error response

            all_records.extend(resp.records)
            offset += len(resp.records)

            # Stop if we've fetched everything
            if len(resp.records) < batch_limit or len(all_records) >= resp.total:
                break

        return ApiResponse(
            records=all_records,
            total=len(all_records),
            source="data.gov.in",
            resource_id=resource_id,
            filters_used=filters,
        )

    # ── Multi-source parallel fetch ───────────────────────────────────────

    async def fetch_multi(
        self, queries: dict[str, dict]
    ) -> dict[str, ApiResponse]:
        """Fetch from multiple resources in parallel.

        Args:
            queries: Mapping of label → {"resource_id": ..., "filters": ..., "limit": ...}

        Returns:
            Mapping of label → ApiResponse.
        """
        async def _do(label: str, q: dict) -> tuple[str, ApiResponse]:
            resp = await self.fetch(
                resource_id=q["resource_id"],
                filters=q.get("filters", {}),
                limit=q.get("limit", 1000),
            )
            return label, resp

        tasks = [_do(label, q) for label, q in queries.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for item in results:
            if isinstance(item, Exception):
                logger.error("Parallel fetch exception: %s", item)
                continue
            label, resp = item
            output[label] = resp

        return output

    # ── Relaxed fetch (broader filters on no results) ─────────────────────

    async def fetch_with_fallback(
        self,
        resource_id: str,
        filters: dict[str, Any],
        relax_keys: list[str],
        limit: int = 1000,
    ) -> ApiResponse:
        """Fetch data, and if empty, relax filters progressively.

        Args:
            resource_id: Resource to query.
            filters: Full filter set.
            relax_keys: Keys to remove one-by-one if no results (e.g., ["district_name", "season"]).
            limit: Record limit.
        """
        resp = await self.fetch(resource_id, filters, limit)
        if resp.ok:
            return resp

        # Progressively relax filters
        relaxed = dict(filters)
        for key in relax_keys:
            if key in relaxed:
                removed_val = relaxed.pop(key)
                logger.info(
                    "Relaxing filter: removed %s=%s for %s",
                    key, removed_val, resource_id,
                )
                resp = await self.fetch(resource_id, relaxed, limit)
                if resp.ok:
                    return resp

        return resp  # Return last (possibly empty) response

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(resource_id: str, filters: dict, limit: int, offset: int) -> str:
        """Generate deterministic cache key."""
        raw = json.dumps(
            {"r": resource_id, "f": filters, "l": limit, "o": offset},
            sort_keys=True,
        )
        return f"dgov:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()
        logger.info("DataGovClient closed")


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: Optional[DataGovClient] = None


def get_client() -> DataGovClient:
    """Get or create the global DataGovClient instance."""
    global _client
    if _client is None:
        _client = DataGovClient()
    return _client
