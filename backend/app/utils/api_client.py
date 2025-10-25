"""
Multi-source API client for data.gov.in with parallel query support.
Handles multiple API keys and enables cross-domain queries.
"""
import asyncio
import hashlib
import json
from typing import Any, Optional
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from app.core.data_sources import (
    DataSource, DataSourceType, DataCategory,
    get_data_source_registry
)
from app.db.models import APICache

load_dotenv()


class DataGovAPIClient:
    """
    Client for querying data.gov.in API across multiple data sources.
    Supports caching and parallel queries.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize API client.
        
        Args:
            db: Database session for caching (optional)
        """
        self.registry = get_data_source_registry()
        self.db = db
        self.timeout = int(os.getenv("API_REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("API_MAX_RETRIES", "3"))
    
    def _generate_cache_key(self, endpoint: str, params: dict) -> str:
        """Generate cache key from endpoint and parameters."""
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{endpoint}:{params_str}".encode()).hexdigest()
    
    def _get_cached_response(self, endpoint: str, params: dict) -> Optional[dict]:
        """Get cached API response if available and not expired."""
        if not self.db:
            return None
        
        cache_key = self._generate_cache_key(endpoint, params)
        
        cache_entry = self.db.query(APICache).filter(
            APICache.endpoint == endpoint,
            APICache.params_hash == cache_key,
            APICache.expires_at > datetime.utcnow()
        ).first()
        
        if cache_entry:
            return cache_entry.response_data
        
        return None
    
    def _cache_response(self, endpoint: str, params: dict, response: dict):
        """Cache API response."""
        if not self.db:
            return
        
        cache_key = self._generate_cache_key(endpoint, params)
        cache_ttl = int(os.getenv("API_CACHE_TTL", "3600"))
        expires_at = datetime.utcnow() + timedelta(seconds=cache_ttl)
        
        # Delete old cache entry if exists
        self.db.query(APICache).filter(
            APICache.endpoint == endpoint,
            APICache.params_hash == cache_key
        ).delete()
        
        # Create new cache entry
        cache_entry = APICache(
            endpoint=endpoint,
            params_hash=cache_key,
            response_data=response,
            expires_at=expires_at
        )
        self.db.add(cache_entry)
        self.db.commit()
    
    async def _make_request(
        self,
        source: DataSource,
        filters: dict[str, Any],
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """
        Make API request to a specific data source.
        
        Args:
            source: DataSource configuration
            filters: Query filters (e.g., {"state_name": "Punjab", "year": 2020})
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            API response as dict
        """
        # Build URL
        url = f"{source.base_url}/{source.resource_id}"
        
        # Build query parameters
        params = {
            "api-key": source.api_key,
            "format": "json",
            "limit": limit,
            "offset": offset
        }
        
        # Add filters
        for key, value in filters.items():
            if key in source.can_filter_by:
                params[f"filters[{key}]"] = value
        
        # Check cache first
        cached = self._get_cached_response(url, params)
        if cached:
            return cached
        
        # Make API request with retries
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Cache the response
                    self._cache_response(url, params, data)
                    
                    return data
                
                except httpx.HTTPError as e:
                    if attempt == self.max_retries - 1:
                        raise Exception(f"API request failed after {self.max_retries} attempts: {e}")
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return {}
    
    async def query_source(
        self,
        source_type: DataSourceType,
        filters: dict[str, Any],
        limit: int = 100
    ) -> dict:
        """
        Query a single data source.
        
        Args:
            source_type: Type of data source to query
            filters: Query filters
            limit: Maximum number of results
            
        Returns:
            Query results with metadata
        """
        source = self.registry.get_source(source_type)
        if not source:
            raise ValueError(f"Data source {source_type} not configured")
        
        data = await self._make_request(source, filters, limit)
        
        return {
            "source": source.name,
            "source_type": source_type.value,
            "category": source.category.value,
            "filters": filters,
            "data": data.get("records", []),
            "total": data.get("total", 0),
            "metadata": {
                "fields": source.fields,
                "resource_id": source.resource_id
            }
        }
    
    async def query_multiple_sources(
        self,
        queries: list[dict[str, Any]]
    ) -> list[dict]:
        """
        Query multiple data sources in parallel.
        
        Args:
            queries: List of query configurations, each with:
                - source_type: DataSourceType
                - filters: dict of filters
                - limit: optional limit
        
        Returns:
            List of results from all queries
        
        Example:
            queries = [
                {
                    "source_type": DataSourceType.CROP_PRODUCTION,
                    "filters": {"state_name": "Punjab", "crop_year": 2020}
                },
                {
                    "source_type": DataSourceType.RAINFALL,
                    "filters": {"state_name": "Punjab", "year": 2020}
                }
            ]
        """
        tasks = []
        for query in queries:
            source_type = query["source_type"]
            filters = query.get("filters", {})
            limit = query.get("limit", 100)
            
            task = self.query_source(source_type, filters, limit)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "error": str(result),
                    "query": queries[i]
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def query_crop_weather_correlation(
        self,
        state: str,
        year: int,
        crop: Optional[str] = None,
        district: Optional[str] = None
    ) -> dict:
        """
        Query both crop production and weather data for correlation analysis.
        This is a convenience method for the common use case of analyzing
        crop production in relation to weather patterns.
        
        Args:
            state: State name
            year: Year to query
            crop: Specific crop (optional)
            district: Specific district (optional)
            
        Returns:
            Combined results from agriculture and meteorology sources
        """
        queries = []
        
        # Crop production query
        crop_filters = {"state_name": state, "crop_year": year}
        if crop:
            crop_filters["crop"] = crop
        if district:
            crop_filters["district_name"] = district
        
        queries.append({
            "source_type": DataSourceType.CROP_PRODUCTION,
            "filters": crop_filters
        })
        
        # Rainfall query
        rain_filters = {"state_name": state, "year": year}
        if district:
            rain_filters["district_name"] = district
        
        if self.registry.is_source_available(DataSourceType.RAINFALL):
            queries.append({
                "source_type": DataSourceType.RAINFALL,
                "filters": rain_filters
            })
        
        # Temperature query (if available)
        if self.registry.is_source_available(DataSourceType.TEMPERATURE):
            queries.append({
                "source_type": DataSourceType.TEMPERATURE,
                "filters": rain_filters
            })
        
        results = await self.query_multiple_sources(queries)
        
        return {
            "state": state,
            "year": year,
            "crop": crop,
            "district": district,
            "results": results,
            "analysis_ready": True
        }
    
    def get_available_sources(self) -> dict[str, list[str]]:
        """
        Get information about available data sources.
        
        Returns:
            Dict with source categories and their available types
        """
        sources = self.registry.get_all_sources()
        
        categorized = {}
        for source in sources:
            category = source.category.value
            if category not in categorized:
                categorized[category] = []
            
            categorized[category].append({
                "type": source.source_type.value,
                "name": source.name,
                "description": source.description,
                "fields": source.fields,
                "can_filter_by": source.can_filter_by
            })
        
        return categorized


def get_api_client(db: Optional[Session] = None) -> DataGovAPIClient:
    """
    Factory function to create API client instance.
    
    Args:
        db: Database session for caching
        
    Returns:
        DataGovAPIClient instance
    """
    return DataGovAPIClient(db=db)
