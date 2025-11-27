"""Unified schemas for all data sources."""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class DataSourceParams(BaseModel):
    """Base params for all data sources."""
    state: Optional[str] = None
    district: Optional[str] = None
    limit: int = 5000


class DailyPriceParams(DataSourceParams):
    """Daily market price parameters."""
    state_keyword: Optional[str] = Field(None, description="State name")
    district: Optional[str] = None
    market: Optional[str] = None
    commodity: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None


class VarietyPriceParams(DataSourceParams):
    """Variety-wise price parameters."""
    State: Optional[str] = Field(None, description="State name (capital S)")
    District: Optional[str] = Field(None, description="District name (capital D)")
    Commodity: Optional[str] = Field(None, description="Commodity name (capital C)")
    Arrival_Date: Optional[str] = Field(None, description="Arrival date")


class ProductionParams(BaseModel):
    """Crop production parameters."""
    state_name: Optional[str] = Field(None, description="State name")
    district_name: Optional[str] = Field(None, description="District name")
    crop: Optional[str] = Field(None, description="Crop name")
    crop_year: Optional[int] = Field(None, description="Crop year")
    season: Optional[str] = Field(None, description="Season: Kharif, Rabi, Summer, Whole Year")
    area_: Optional[float] = Field(None, description="Area in hectares")
    production_: Optional[float] = Field(None, description="Production in tonnes")
    limit: int = 5000


class TemperatureParams(BaseModel):
    """Temperature series parameters."""
    year: Optional[int] = None
    annual: Optional[str] = Field(None, alias="_annual")
    jan_feb: Optional[str] = Field(None, alias="_jan_feb")
    mar_may: Optional[str] = Field(None, alias="_mar_may")
    jun_sep: Optional[str] = Field(None, alias="_jun_sep")
    oct_dec: Optional[str] = Field(None, alias="_oct_dec")
    limit: int = 5000


class RainfallParams(BaseModel):
    """Rainfall subdivision parameters."""
    subdivision: Optional[str] = None
    year: Optional[int] = None
    limit: int = 5000


class QueryIntent(BaseModel):
    """Detected query intent and parameters."""
    query_type: Literal["comparison", "trend", "correlation", "policy", "ranking", "general"]
    entities: list[str] = Field(default_factory=list, description="States, districts, crops mentioned")
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    metrics: list[str] = Field(default_factory=list, description="production, rainfall, price, etc")
    
    # Extracted params for each source
    daily_price_params: Optional[DailyPriceParams] = None
    variety_price_params: Optional[VarietyPriceParams] = None
    production_params: Optional[ProductionParams] = None
    temperature_params: Optional[TemperatureParams] = None
    rainfall_params: Optional[RainfallParams] = None
