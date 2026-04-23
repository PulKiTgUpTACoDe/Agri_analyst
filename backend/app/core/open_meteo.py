import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger("agri.open_meteo")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


@dataclass
class WeatherResponse:
    """Unified weather response."""
    records: list[dict] = field(default_factory=list)
    location: dict = field(default_factory=dict)
    variables: list[str] = field(default_factory=list)
    time_range: dict = field(default_factory=dict)
    source: str = "open-meteo"
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.records) > 0


class OpenMeteoClient:
    """Async client for Open-Meteo weather API."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            follow_redirects=True,
        )
        self._cache = None

    def set_cache(self, cache):
        self._cache = cache

    async def get_current_weather(
        self, latitude: float, longitude: float, location_name: str = ""
    ) -> WeatherResponse:
        """Get current weather conditions."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure",
            "timezone": "Asia/Kolkata",
        }
        return await self._fetch(FORECAST_URL, params, location_name, "current")

    async def get_historical(
        self, latitude: float, longitude: float,
        start_date: str, end_date: str,
        variables: Optional[list[str]] = None,
        daily: bool = True, location_name: str = "",
    ) -> WeatherResponse:
        """Get historical weather data (ERA5-Land, from 1940)."""
        if variables is None:
            variables = [
                "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                "precipitation_sum", "rain_sum", "et0_fao_evapotranspiration",
                "wind_speed_10m_max",
            ]
        time_key = "daily" if daily else "hourly"
        params = {
            "latitude": latitude, "longitude": longitude,
            "start_date": start_date, "end_date": end_date,
            time_key: ",".join(variables),
            "timezone": "Asia/Kolkata",
        }
        return await self._fetch(ARCHIVE_URL, params, location_name, time_key)

    async def get_forecast(
        self, latitude: float, longitude: float,
        days: int = 7, location_name: str = "",
    ) -> WeatherResponse:
        """Get weather forecast for agricultural planning."""
        params = {
            "latitude": latitude, "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,et0_fao_evapotranspiration,uv_index_max",
            "forecast_days": str(min(days, 16)),
            "timezone": "Asia/Kolkata",
        }
        return await self._fetch(FORECAST_URL, params, location_name, "daily")

    async def get_rainfall_summary(
        self, latitude: float, longitude: float,
        start_date: str, end_date: str, location_name: str = "",
    ) -> WeatherResponse:
        """Get daily rainfall – replaces the static rainfall dataset."""
        return await self.get_historical(
            latitude, longitude, start_date, end_date,
            variables=["precipitation_sum", "rain_sum"],
            daily=True, location_name=location_name,
        )

    async def get_temperature_summary(
        self, latitude: float, longitude: float,
        start_date: str, end_date: str, location_name: str = "",
    ) -> WeatherResponse:
        """Get daily temperature – replaces the static temperature dataset."""
        return await self.get_historical(
            latitude, longitude, start_date, end_date,
            variables=["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean"],
            daily=True, location_name=location_name,
        )

    async def _fetch(
        self, url: str, params: dict[str, Any],
        location_name: str, data_type: str = "daily",
    ) -> WeatherResponse:
        """Execute HTTP request and parse Open-Meteo response."""
        start = time.monotonic()
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            elapsed = (time.monotonic() - start) * 1000

            records = self._parse_response(data, data_type)
            var_keys = list(data.get(data_type, {}).keys()) if data_type != "current" else list(data.get("current", {}).keys())

            result = WeatherResponse(
                records=records,
                location={"name": location_name, "latitude": data.get("latitude"),
                           "longitude": data.get("longitude"), "elevation": data.get("elevation"),
                           "timezone": data.get("timezone")},
                variables=var_keys,
                time_range={"start": params.get("start_date", "now"), "end": params.get("end_date", "now")},
                elapsed_ms=round(elapsed, 1),
            )
            logger.info("Open-Meteo: %d records for %s in %.0fms", len(records), location_name or "location", elapsed)
            return result

        except httpx.HTTPStatusError as exc:
            elapsed = (time.monotonic() - start) * 1000
            error_msg = f"Open-Meteo HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.error(error_msg)
            return WeatherResponse(elapsed_ms=round(elapsed, 1), error=error_msg)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Open-Meteo error: %s", exc)
            return WeatherResponse(elapsed_ms=round(elapsed, 1), error=str(exc))

    @staticmethod
    def _parse_response(data: dict, data_type: str) -> list[dict]:
        """Convert Open-Meteo columnar format to list of row dicts."""
        if data_type == "current":
            current = data.get("current", {})
            return [current] if current else []

        block = data.get(data_type, {})
        if not block:
            return []

        times = block.get("time", [])
        if not times:
            return []

        records = []
        for i, t in enumerate(times):
            row = {"date": t}
            for key, values in block.items():
                if key == "time":
                    continue
                if isinstance(values, list) and i < len(values):
                    row[key] = values[i]
            records.append(row)
        return records

    async def close(self):
        await self.client.aclose()
        logger.info("OpenMeteoClient closed")


_meteo_client: Optional[OpenMeteoClient] = None


def get_meteo_client() -> OpenMeteoClient:
    global _meteo_client
    if _meteo_client is None:
        _meteo_client = OpenMeteoClient()
    return _meteo_client
