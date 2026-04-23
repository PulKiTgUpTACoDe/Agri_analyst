"""Unified schemas for all data sources and query intent."""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date


class DailyPriceParams(BaseModel):
    """Daily market price parameters."""
    state: Optional[str] = Field(None, description="State name")
    district: Optional[str] = None
    market: Optional[str] = None
    commodity: Optional[str] = None
    variety: Optional[str] = None

class VarietyPriceParams(BaseModel):
    """Variety-wise price parameters."""
    state: Optional[str] = Field(None, description="State name")
    district: Optional[str] = None
    commodity: Optional[str] = None

class ProductionParams(BaseModel):
    """Crop production parameters."""
    state_name: Optional[str] = Field(None, description="State name")
    district_name: Optional[str] = Field(None, description="District name")
    crop: Optional[str] = Field(None, description="Crop name")
    crop_year: Optional[int] = Field(None, description="Crop year")
    season: Optional[str] = Field(None, description="Season: Kharif, Rabi, Summer, Whole Year")

class WeatherParams(BaseModel):
    """Weather data parameters (for Open-Meteo)."""
    state: Optional[str] = Field(None, description="State name for weather lookup")
    district: Optional[str] = Field(None, description="District name for more precise weather")
    subdivision: Optional[str] = Field(None, description="Rainfall subdivision name")
    start_year: Optional[int] = Field(None, description="Start year for historical data")
    end_year: Optional[int] = Field(None, description="End year for historical data")
    include_forecast: bool = Field(False, description="Whether to include weather forecast")
    include_current: bool = Field(False, description="Whether to include current weather")


class QueryIntent(BaseModel):
    """Detected query intent and parameters."""
    query_type: Literal["comparison", "trend", "correlation", "policy", "ranking", "forecast", "current_weather", "general"]
    entities: list[str] = Field(default_factory=list, description="States, districts, crops mentioned")
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    metrics: list[str] = Field(default_factory=list, description="production, rainfall, price, temperature, etc")
    
    # Extracted params for each source
    daily_price_params: Optional[DailyPriceParams] = None
    variety_price_params: Optional[VarietyPriceParams] = None
    production_params: Optional[ProductionParams] = None
    weather_params: Optional[WeatherParams] = None


class DataQuality(BaseModel):
    """Data quality report for a single source."""
    source_id: str
    record_count: int = 0
    has_data: bool = False
    error: Optional[str] = None
    freshness: str = "unknown"  # "live", "today", "recent", "historical"
    notes: list[str] = Field(default_factory=list)
