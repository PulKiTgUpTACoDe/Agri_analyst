import logging, time
from dataclasses import dataclass, field
from typing import Any, Optional
import httpx

logger = logging.getLogger("agri.open_meteo")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

@dataclass
class WeatherResponse:
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
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            follow_redirects=True,
        )
        self._cache = None

    def set_cache(self, cache):
        self._cache = cache

    async def get_current_weather(self, lat: float, lon: float, name: str = "") -> WeatherResponse:
        return await self._fetch(FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure",
            "timezone": "Asia/Kolkata",
        }, name, "current")

    async def get_historical(self, lat: float, lon: float, start: str, end: str,
                             variables: list[str] | None = None, daily: bool = True, name: str = "") -> WeatherResponse:
        if variables is None:
            variables = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                         "precipitation_sum", "rain_sum", "et0_fao_evapotranspiration", "wind_speed_10m_max"]
        key = "daily" if daily else "hourly"
        return await self._fetch(ARCHIVE_URL, {
            "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
            key: ",".join(variables), "timezone": "Asia/Kolkata",
        }, name, key)

    async def get_forecast(self, lat: float, lon: float, days: int = 7, name: str = "") -> WeatherResponse:
        return await self._fetch(FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,et0_fao_evapotranspiration,uv_index_max",
            "forecast_days": str(min(days, 16)), "timezone": "Asia/Kolkata",
        }, name, "daily")

    async def get_rainfall_summary(self, lat: float, lon: float, start: str, end: str, name: str = "") -> WeatherResponse:
        return await self.get_historical(lat, lon, start, end, ["precipitation_sum", "rain_sum"], name=name)

    async def get_temperature_summary(self, lat: float, lon: float, start: str, end: str, name: str = "") -> WeatherResponse:
        return await self.get_historical(lat, lon, start, end, ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean"], name=name)

    async def _fetch(self, url: str, params: dict[str, Any], name: str, data_type: str = "daily") -> WeatherResponse:
        start = time.monotonic()
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            elapsed = (time.monotonic() - start) * 1000
            records = self._parse(data, data_type)
            result = WeatherResponse(
                records=records,
                location={"name": name, "latitude": data.get("latitude"), "longitude": data.get("longitude"),
                           "elevation": data.get("elevation"), "timezone": data.get("timezone")},
                variables=list(data.get(data_type, data.get("current", {})).keys()),
                time_range={"start": params.get("start_date", "now"), "end": params.get("end_date", "now")},
                elapsed_ms=round(elapsed, 1),
            )
            logger.info("Open-Meteo: %d records for %s in %.0fms", len(records), name or "loc", elapsed)
            return result
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Open-Meteo error: %s", e)
            return WeatherResponse(elapsed_ms=round(elapsed, 1), error=str(e))

    @staticmethod
    def _parse(data: dict, data_type: str) -> list[dict]:
        if data_type == "current":
            c = data.get("current", {})
            return [c] if c else []
        block = data.get(data_type, {})
        times = block.get("time", [])
        if not times:
            return []
        return [{"date": times[i], **{k: v[i] for k, v in block.items() if k != "time" and isinstance(v, list) and i < len(v)}}
                for i in range(len(times))]

    async def close(self):
        await self.client.aclose()

_meteo_client: Optional[OpenMeteoClient] = None

def get_meteo_client() -> OpenMeteoClient:
    global _meteo_client
    if _meteo_client is None:
        _meteo_client = OpenMeteoClient()
    return _meteo_client
