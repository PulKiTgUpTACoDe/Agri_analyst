"""Data source registry – single source of truth for all API endpoints.

Adding a new data source is a config change, not a code change.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("agri.data_sources")


@dataclass
class DataSource:
    """Definition of a single data source."""
    id: str                                    # e.g., "daily_prices"
    name: str                                  # e.g., "Daily Market Prices"
    icon: str                                  # emoji for citations
    source_type: str                           # "data_gov" | "open_meteo"
    resource_id: Optional[str] = None          # data.gov.in resource ID
    description: str = ""
    update_frequency: str = "daily"            # "realtime" | "daily" | "monthly" | "historical"
    cache_category: str = "default"            # maps to cache TTL category
    available_filters: list[str] = field(default_factory=list)
    field_mapping: dict[str, str] = field(default_factory=dict)  # normalize field names


# ── Registry of all data sources ──────────────────────────────────────────────

ALL_SOURCES: dict[str, DataSource] = {
    "daily_prices": DataSource(
        id="daily_prices",
        name="Daily Market Prices",
        icon="💰",
        source_type="data_gov",
        resource_id="9ef84268-d588-465a-a308-a864a43d0070",
        description="Current daily commodity prices from regulated mandis across India",
        update_frequency="daily",
        cache_category="daily_prices",
        available_filters=["state.keyword", "district", "market", "commodity", "variety", "grade"],
        field_mapping={
            "state.keyword": "state",
            "modal_price": "price",
            "min_price": "min_price",
            "max_price": "max_price",
        },
    ),
    "variety_prices": DataSource(
        id="variety_prices",
        name="Variety-wise Prices",
        icon="🏷️",
        source_type="data_gov",
        resource_id="35985678-0d79-46b4-9ed6-6f13308a1d24",
        description="Variety-wise daily market prices of commodities",
        update_frequency="daily",
        cache_category="variety_prices",
        available_filters=["State", "District", "Commodity", "Arrival_Date"],
        field_mapping={
            "State": "state",
            "District": "district",
            "Modal_Price": "price",
            "Commodity": "commodity",
        },
    ),
    "crop_production": DataSource(
        id="crop_production",
        name="Crop Production Statistics",
        icon="🌾",
        source_type="data_gov",
        resource_id="35be999b-0208-4354-b557-f6ca9a5355de",
        description="District-wise, season-wise crop production statistics from 1997",
        update_frequency="monthly",
        cache_category="crop_production",
        available_filters=["state_name", "district_name", "crop", "crop_year", "season"],
        field_mapping={
            "State_Name": "state",
            "state_name": "state",
            "District_Name": "district",
            "district_name": "district",
            "Crop_Year": "year",
            "crop_year": "year",
            "Production": "production",
            "Area": "area",
        },
    ),
    # ── Open-Meteo sources (replace static temperature/rainfall) ──────
    "weather_current": DataSource(
        id="weather_current",
        name="Current Weather",
        icon="☀️",
        source_type="open_meteo",
        description="Real-time weather conditions for any Indian location",
        update_frequency="realtime",
        cache_category="weather_current",
        available_filters=["state", "district"],
    ),
    "weather_historical": DataSource(
        id="weather_historical",
        name="Historical Weather Data",
        icon="📊",
        source_type="open_meteo",
        description="Historical weather data from 1940-present (ERA5-Land reanalysis)",
        update_frequency="daily",
        cache_category="weather_historical",
        available_filters=["state", "district", "start_date", "end_date"],
    ),
    "temperature_data": DataSource(
        id="temperature_data",
        name="Temperature Data",
        icon="🌡️",
        source_type="open_meteo",
        description="Historical and current temperature data for Indian locations",
        update_frequency="daily",
        cache_category="weather_historical",
        available_filters=["state", "district", "start_date", "end_date"],
    ),
    "rainfall_data": DataSource(
        id="rainfall_data",
        name="Rainfall Data",
        icon="🌧️",
        source_type="open_meteo",
        description="Historical and current rainfall/precipitation data",
        update_frequency="daily",
        cache_category="weather_historical",
        available_filters=["state", "district", "subdivision", "start_date", "end_date"],
    ),
    "weather_forecast": DataSource(
        id="weather_forecast",
        name="Weather Forecast",
        icon="🔮",
        source_type="open_meteo",
        description="7-day weather forecast for agricultural planning",
        update_frequency="realtime",
        cache_category="weather_forecast",
        available_filters=["state", "district"],
    ),
}


class DataSourceRegistry:
    """Registry for looking up data sources."""

    def __init__(self):
        self.sources = dict(ALL_SOURCES)

    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a data source by ID."""
        return self.sources.get(source_id)

    def list_all(self) -> list[DataSource]:
        """List all registered data sources."""
        return list(self.sources.values())

    def get_data_gov_sources(self) -> list[DataSource]:
        """Get only data.gov.in sources."""
        return [s for s in self.sources.values() if s.source_type == "data_gov"]

    def get_weather_sources(self) -> list[DataSource]:
        """Get only Open-Meteo weather sources."""
        return [s for s in self.sources.values() if s.source_type == "open_meteo"]

    def get_source_map(self) -> dict[str, dict]:
        """Get source metadata for citation building."""
        return {
            s.id: {"name": s.name, "icon": s.icon, "description": s.description}
            for s in self.sources.values()
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[DataSourceRegistry] = None


def get_registry() -> DataSourceRegistry:
    """Get or create the global DataSourceRegistry."""
    global _registry
    if _registry is None:
        _registry = DataSourceRegistry()
    return _registry
