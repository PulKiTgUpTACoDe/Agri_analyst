from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DataSource:
    id: str
    name: str
    icon: str
    source_type: str
    resource_id: Optional[str] = None
    description: str = ""
    update_frequency: str = "daily"
    cache_category: str = "default"
    available_filters: list[str] = field(default_factory=list)
    field_mapping: dict[str, str] = field(default_factory=dict)

ALL_SOURCES: dict[str, DataSource] = {
    "daily_prices": DataSource(
        id="daily_prices", name="Daily Market Prices", icon="💰", source_type="data_gov",
        resource_id="9ef84268-d588-465a-a308-a864a43d0070",
        description="Current daily commodity prices from regulated mandis",
        cache_category="daily_prices",
        available_filters=["state.keyword", "district", "market", "commodity", "variety", "grade"],
    ),
    "variety_prices": DataSource(
        id="variety_prices", name="Variety-wise Prices", icon="🏷️", source_type="data_gov",
        resource_id="35985678-0d79-46b4-9ed6-6f13308a1d24",
        description="Variety-wise daily market prices",
        cache_category="variety_prices",
        available_filters=["State", "District", "Commodity", "Arrival_Date"],
    ),
    "crop_production": DataSource(
        id="crop_production", name="Crop Production Statistics", icon="🌾", source_type="data_gov",
        resource_id="35be999b-0208-4354-b557-f6ca9a5355de",
        description="District-wise crop production statistics from 1997",
        update_frequency="monthly", cache_category="crop_production",
        available_filters=["state_name", "district_name", "crop", "crop_year", "season"],
    ),
    "weather_current": DataSource(
        id="weather_current", name="Current Weather", icon="☀️", source_type="open_meteo",
        description="Real-time weather conditions", update_frequency="realtime",
        cache_category="weather_current", available_filters=["state", "district"],
    ),
    "weather_historical": DataSource(
        id="weather_historical", name="Historical Weather", icon="📊", source_type="open_meteo",
        description="Historical weather data from 1940-present",
        cache_category="weather_historical",
        available_filters=["state", "district", "start_date", "end_date"],
    ),
    "temperature_data": DataSource(
        id="temperature_data", name="Temperature Data", icon="🌡️", source_type="open_meteo",
        description="Temperature data for Indian locations",
        cache_category="weather_historical",
        available_filters=["state", "district", "start_date", "end_date"],
    ),
    "rainfall_data": DataSource(
        id="rainfall_data", name="Rainfall Data", icon="🌧️", source_type="open_meteo",
        description="Rainfall/precipitation data",
        cache_category="weather_historical",
        available_filters=["state", "district", "subdivision", "start_date", "end_date"],
    ),
    "weather_forecast": DataSource(
        id="weather_forecast", name="Weather Forecast", icon="🔮", source_type="open_meteo",
        description="7-day weather forecast for agriculture",
        update_frequency="realtime", cache_category="weather_forecast",
        available_filters=["state", "district"],
    ),
}

class DataSourceRegistry:
    def __init__(self):
        self.sources = dict(ALL_SOURCES)

    def get_source(self, source_id: str) -> Optional[DataSource]:
        return self.sources.get(source_id)

    def list_all(self) -> list[DataSource]:
        return list(self.sources.values())

    def get_source_map(self) -> dict[str, dict]:
        return {s.id: {"name": s.name, "icon": s.icon, "description": s.description} for s in self.sources.values()}

_registry: Optional[DataSourceRegistry] = None

def get_registry() -> DataSourceRegistry:
    global _registry
    if _registry is None:
        _registry = DataSourceRegistry()
    return _registry
