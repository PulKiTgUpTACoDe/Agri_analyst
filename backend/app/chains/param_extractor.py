import os
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


class DailyPricesParams(BaseModel):
    state_keyword: Optional[str] = Field(None, description="maps to filters[state.keyword]")
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


def make_param_extractor(schema_model: Type[BaseModel]):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Extract API parameters from the user's question. Output ONLY the specified JSON schema."),
        ("human", "{question}"),
    ])
    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
    )
    return prompt | model.with_structured_output(schema_model)
