"""LangGraph workflow definition.

Flow:
1. detect_intent → determine what user wants
2. select_sources → pick which APIs to call (conditional: skip if general)
3. fetch_data → parallel API calls (data.gov.in + Open-Meteo)
4. validate_data → check data quality
5. analyze_data → statistical analysis
6. generate_answer → LLM synthesizes final response
"""
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import (
    detect_intent, select_sources, fetch_data,
    validate_data, analyze_data, generate_answer,
)


def should_fetch_data(state: AgentState) -> str:
    """Route: does the query need external data or is it general?"""
    intent = state.get("intent")
    if not intent:
        return "answer_directly"

    needs_data = any([
        intent.daily_price_params,
        intent.variety_price_params,
        intent.production_params,
        intent.weather_params,
    ])

    return "select_sources" if needs_data else "answer_directly"


def is_data_sufficient(state: AgentState) -> str:
    """Route: do we have enough data to analyze, or skip to answer?"""
    raw_data = state.get("raw_data", {})
    total = sum(len(v) for v in raw_data.values())

    if total > 0:
        return "analyze"
    return "answer_directly"


def create_workflow() -> StateGraph:
    """Create the agricultural analysis workflow."""
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("select_sources", select_sources)
    workflow.add_node("fetch_data", fetch_data)
    workflow.add_node("validate_data", validate_data)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("generate_answer", generate_answer)

    # Entry point
    workflow.set_entry_point("detect_intent")

    # Conditional: needs data or answer directly?
    workflow.add_conditional_edges(
        "detect_intent",
        should_fetch_data,
        {
            "select_sources": "select_sources",
            "answer_directly": "generate_answer",
        }
    )

    # Data pipeline: select → fetch → validate → conditional
    workflow.add_edge("select_sources", "fetch_data")
    workflow.add_edge("fetch_data", "validate_data")

    # After validation: analyze if data exists, otherwise answer directly
    workflow.add_conditional_edges(
        "validate_data",
        is_data_sufficient,
        {
            "analyze": "analyze_data",
            "answer_directly": "generate_answer",
        }
    )

    # Analysis → answer
    workflow.add_edge("analyze_data", "generate_answer")

    # Final
    workflow.add_edge("generate_answer", END)

    return workflow.compile()


_workflow = None

def get_workflow():
    """Get or create workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow
