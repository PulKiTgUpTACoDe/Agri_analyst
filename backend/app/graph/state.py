"""LangGraph state definition."""
from typing import TypedDict
from app.core.schemas import QueryIntent


class AgentState(TypedDict):
    """State passed through the graph."""
    question: str
    intent: QueryIntent | None
    sources_selected: list[str]           # which data sources to query
    raw_data: dict[str, list[dict]]
    data_quality: dict[str, dict]         # validation results per source
    analysis: dict | None
    answer: str | None
    metadata: dict
    errors: list[str]                     # accumulated errors
    timing: dict[str, float]              # per-node latency (ms)
