"""LangGraph state definition."""
from typing import TypedDict
from app.core.schemas import QueryIntent


class AgentState(TypedDict):
    """State passed through the graph."""
    question: str
    intent: QueryIntent | None
    raw_data: dict[str, list[dict]]
    analysis: dict | None
    answer: str | None
    metadata: dict
    context_docs: list[dict] | None  # Retrieved documents from vector store
