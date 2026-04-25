from pydantic import BaseModel, Field
from typing import Optional, Literal

class DailyPriceParams(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    market: Optional[str] = None
    commodity: Optional[str] = None
    variety: Optional[str] = None

class VarietyPriceParams(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    commodity: Optional[str] = None

class ProductionParams(BaseModel):
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    crop: Optional[str] = None
    crop_year: Optional[int] = None
    season: Optional[str] = None

class WeatherParams(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    subdivision: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD, overrides start_year")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD, overrides end_year")
    include_forecast: bool = False
    include_current: bool = False

class QueryIntent(BaseModel):
    query_type: Literal["comparison", "trend", "correlation", "policy", "ranking", "forecast", "current_weather", "general"]
    entities: list[str] = Field(default_factory=list)
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    metrics: list[str] = Field(default_factory=list)
    daily_price_params: Optional[DailyPriceParams] = None
    variety_price_params: Optional[VarietyPriceParams] = None
    production_params: Optional[ProductionParams] = None
    weather_params: Optional[WeatherParams] = None

class DataQuality(BaseModel):
    source_id: str
    record_count: int = 0
    has_data: bool = False
    error: Optional[str] = None
    freshness: str = "unknown"
    notes: list[str] = Field(default_factory=list)
