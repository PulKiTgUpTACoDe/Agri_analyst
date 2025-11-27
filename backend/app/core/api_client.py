"""Unified API client for all data.gov.in endpoints."""
import httpx
from typing import Any, Optional
from app.core.config import get_settings


class DataGovClient:
    """Unified API client for data.gov.in."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def fetch(self, endpoint: str, filters: dict[str, Any], limit: int = 5000) -> list[dict]:
        """Fetch data with automatic filter."""
        params = {
            "api-key": self.settings.GOV_API_KEY,
            "format": "json",
            "limit": str(limit),
            **{f"filters[{k}]": str(v) for k, v in filters.items() if v is not None}
        }
        
        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            records = response.json().get("records", [])
            
            # Relax filters if no results
            if not records and filters:
                for key in ['state', 'state_name', 'crop', 'commodity']:
                    if key in filters:
                        return await self.fetch(endpoint, {key: filters[key]}, limit)
            
            return records
        except Exception as e:
            print(f"[API_ERROR] {e}")
            return []
    
    async def close(self):
        await self.client.aclose()


# Global client instance
_client: Optional[DataGovClient] = None


def get_client() -> DataGovClient:
    global _client
    if _client is None:
        _client = DataGovClient()
    return _client
