import asyncio, hashlib, json, logging, time
from dataclasses import dataclass, field
from typing import Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from app.core.config import get_settings

logger = logging.getLogger("agri.api_client")

@dataclass
class ApiResponse:
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

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

class RetryableAPIError(Exception): pass
class PermanentAPIError(Exception): pass

DATA_GOV_BASE = "https://api.data.gov.in/resource"

class DataGovClient:
    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
        )
        self._cache = None

    def set_cache(self, cache):
        self._cache = cache

    @retry(retry=retry_if_exception_type(RetryableAPIError), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=1, max=16),
           before_sleep=before_sleep_log(logger, logging.WARNING), reraise=True)
    async def _raw_fetch(self, resource_id: str, filters: dict[str, Any], limit: int, offset: int) -> dict:
        params = {"api-key": self.settings.GOV_API_KEY, "format": "json", "limit": str(limit), "offset": str(offset)}
        for k, v in filters.items():
            if v is not None:
                params[f"filters[{k}]"] = str(v)
        url = f"{DATA_GOV_BASE}/{resource_id}"
        try:
            resp = await self.client.get(url, params=params)
            if resp.status_code in RETRYABLE_STATUS:
                raise RetryableAPIError(f"HTTP {resp.status_code} from {resource_id}")
            if resp.status_code == 403:
                raise PermanentAPIError(f"403 Forbidden for {resource_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as e:
            raise RetryableAPIError(f"Timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUS:
                raise RetryableAPIError(str(e)) from e
            raise PermanentAPIError(str(e)) from e

    async def fetch(self, resource_id: str, filters: dict[str, Any], limit: int = 1000, offset: int = 0) -> ApiResponse:
        clean = {k: v for k, v in filters.items() if v is not None and v != ""}
        cache_key = self._make_key(resource_id, clean, limit, offset)
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                cached.from_cache = True
                return cached
        start = time.monotonic()
        try:
            data = await self._raw_fetch(resource_id, clean, limit, offset)
            elapsed = (time.monotonic() - start) * 1000
            records = data.get("records", [])
            result = ApiResponse(records=records, total=int(data.get("total", len(records))),
                                 source="data.gov.in", resource_id=resource_id,
                                 filters_used=clean, elapsed_ms=round(elapsed, 1))
            logger.info("Fetched %d records from %s in %.0fms", len(records), resource_id, elapsed)
            if self._cache and result.ok:
                self._cache.set(cache_key, result)
            return result
        except (RetryableAPIError, PermanentAPIError, Exception) as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Fetch failed for %s: %s", resource_id, e)
            return ApiResponse(source="data.gov.in", resource_id=resource_id,
                               filters_used=clean, elapsed_ms=round(elapsed, 1), error=str(e))

    @staticmethod
    def _make_key(resource_id: str, filters: dict, limit: int, offset: int) -> str:
        raw = json.dumps({"r": resource_id, "f": filters, "l": limit, "o": offset}, sort_keys=True)
        return f"dgov:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    async def close(self):
        await self.client.aclose()

_client: Optional[DataGovClient] = None

def get_client() -> DataGovClient:
    global _client
    if _client is None:
        _client = DataGovClient()
    return _client
