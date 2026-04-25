from typing import TypedDict
from app.core.schemas import QueryIntent

class AgentState(TypedDict):
    question: str
    intent: QueryIntent | None
    sources_selected: list[str]
    raw_data: dict[str, list[dict]]
    data_quality: dict[str, dict]
    analysis: dict | None
    answer: str | None
    metadata: dict
    errors: list[str]
    timing: dict[str, float]
