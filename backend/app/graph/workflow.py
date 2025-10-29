"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import detect_intent, fetch_data, analyze_data, generate_answer


def should_fetch_data(state):
    """Determine if we need to fetch data or can answer directly."""
    intent = state.get("intent")
    if not intent:
        return "answer_directly"
    
    # Check if any data source params are set
    needs_data = any([
        intent.daily_price_params,
        intent.variety_price_params,
        intent.production_params,
        intent.temperature_params,
        intent.rainfall_params
    ])
    
    return "fetch_data" if needs_data else "answer_directly"


def create_workflow() -> StateGraph:
    """Create the agricultural analysis workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("fetch_data", fetch_data)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_node("answer_directly", generate_answer)  
    
    # Define edges
    workflow.set_entry_point("detect_intent")
    
    # Conditional: fetch data only if needed
    workflow.add_conditional_edges(
        "detect_intent",
        should_fetch_data,
        {
            "fetch_data": "fetch_data",
            "answer_directly": "answer_directly"
        }
    )
    
    workflow.add_edge("fetch_data", "analyze_data")
    workflow.add_edge("analyze_data", "generate_answer")
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("answer_directly", END)
    
    return workflow.compile()


# Global workflow instance
_workflow = None


def get_workflow():
    """Get or create workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow
