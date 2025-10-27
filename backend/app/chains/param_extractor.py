import os
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


class DailyPricesParams(BaseModel):
    state_keyword: Optional[str] = None
    district: Optional[str] = None
    market: Optional[str] = None
    commodity: Optional[str] = None
    variety: Optional[str] = None
    grade: Optional[str] = None
    limit: Optional[int] = 50


class VarietyPricesParams(BaseModel):
    State: Optional[str] = None
    District: Optional[str] = None
    Commodity: Optional[str] = None
    Arrival_Date: Optional[str] = Field(None, description="DD/MM/YYYY")
    limit: Optional[int] = 50


class TemperatureSeriesParams(BaseModel):
    year: Optional[int] = None
    _annual: Optional[str] = None
    _jan_feb: Optional[str] = None
    _mar_may: Optional[str] = None
    _jun_sep: Optional[str] = None
    _oct_dec: Optional[str] = None
    limit: Optional[int] = 50


class RainfallSubdivisionsParams(BaseModel):
    limit: Optional[int] = 50


class CropProductionParams(BaseModel):
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    crop_year: Optional[int] = None
    season: Optional[str] = None  # Kharif, Rabi, Summer, Whole Year
    crop: Optional[str] = None
    limit: Optional[int] = 100


class DistrictRainfallParams(BaseModel):
    state_name: Optional[str] = None
    district_name: Optional[str] = None
    year: Optional[int] = None
    month: Optional[str] = None
    subdivision: Optional[str] = None
    limit: Optional[int] = 100


def make_param_extractor(schema_model: Type[BaseModel]):
    system_prompt = """Extract API parameters from the user's question. 
    
Rules:
- Only extract parameters that are explicitly mentioned in the question
- Leave fields as null if not mentioned
- For state names, use proper capitalization (e.g., 'Maharashtra', 'Tamil Nadu')
- For commodity names, use proper capitalization (e.g., 'Tomato', 'Onion', 'Potato')
- If the question is about a specific endpoint (daily prices, variety prices, temperature, rainfall), only extract for that endpoint
- Daily prices questions: extract state_keyword, district, market, commodity, variety, grade
- Variety prices questions: extract State, District, Commodity, Arrival_Date
- Temperature questions: extract year
- Rainfall questions: no specific filters needed
- Crop production questions: extract state_name, district_name, crop_year, season, crop (for production/area/yield queries)
- District rainfall questions: extract state_name, district_name, year, month (for rainfall/precipitation queries)

Output ONLY the specified JSON schema with extracted values."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])
    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )
    return prompt | model.with_structured_output(schema_model)
