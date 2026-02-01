"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import detect_intent, fetch_data, analyze_data, generate_answer, retrieve_context


def should_fetch_data(state):
    """Determine if we need to fetch data or can answer directly."""
    intent = state.get("intent")
    if not intent:
        return "retrieve_and_answer"  # General questions: retrieve context then answer
    
    # Check if any data source params are set
    needs_data = any([
        intent.daily_price_params,
        intent.variety_price_params,
        intent.production_params,
        intent.temperature_params,
        intent.rainfall_params
    ])
    
    return "fetch_data" if needs_data else "retrieve_and_answer"


def create_workflow() -> StateGraph:
    """Create the agricultural analysis workflow.
    
    Flow:
    1. detect_intent -> Check if data fetching is needed
    2a. If needs data: fetch_data -> retrieve_context -> analyze_data -> generate_answer
    2b. If general: retrieve_context -> generate_answer
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("fetch_data", fetch_data)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("retrieve_and_answer", retrieve_context)  # For general questions
    
    # Define edges
    workflow.set_entry_point("detect_intent")
    
    # Conditional routing based on whether data is needed
    workflow.add_conditional_edges(
        "detect_intent",
        should_fetch_data,
        {
            "fetch_data": "fetch_data",
            "retrieve_and_answer": "retrieve_and_answer"
        }
    )
    
    # Data-driven path: fetch -> retrieve context -> analyze -> answer
    workflow.add_edge("fetch_data", "retrieve_context")
    workflow.add_edge("retrieve_context", "analyze_data")
    workflow.add_edge("analyze_data", "generate_answer")
    
    # General question path: retrieve context -> answer
    workflow.add_edge("retrieve_and_answer", "generate_answer")
    
    # Final answer
    workflow.add_edge("generate_answer", END)
    
    return workflow.compile()


_workflow = None

def get_workflow():
    """Get or create workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow
