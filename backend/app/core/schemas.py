"""Unified schemas for all data sources."""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class DataSourceParams(BaseModel):
    """Base params for all data sources."""
    state: Optional[str] = None
    district: Optional[str] = None
    limit: int = 50


class PriceParams(DataSourceParams):
    """Market price parameters."""
    commodity: Optional[str] = None
    market: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None


class ProductionParams(DataSourceParams):
    """Crop production parameters."""
    crop: Optional[str] = None
    crop_year: Optional[int] = None
    season: Optional[Literal["Kharif", "Rabi", "Summer", "Whole Year"]] = None


class ClimateParams(DataSourceParams):
    """Climate data parameters."""
    year: Optional[int] = None
    month: Optional[str] = None
    subdivision: Optional[str] = None


class QueryIntent(BaseModel):
    """Detected query intent and parameters."""
    query_type: Literal["comparison", "trend", "correlation", "policy", "ranking", "general"]
    entities: list[str] = Field(default_factory=list, description="States, districts, crops mentioned")
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    metrics: list[str] = Field(default_factory=list, description="production, rainfall, price, etc")
    
    # Extracted params for each source
    daily_price_params: Optional[PriceParams] = None
    variety_price_params: Optional[PriceParams] = None
    production_params: Optional[ProductionParams] = None
    temperature_params: Optional[ClimateParams] = None
    rainfall_params: Optional[ClimateParams] = None
    district_rainfall_params: Optional[ClimateParams] = None
