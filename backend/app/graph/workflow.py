"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import detect_intent, fetch_data, analyze_data, generate_answer


def create_workflow() -> StateGraph:
    """Create the agricultural analysis workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("detect_intent", detect_intent)
    workflow.add_node("fetch_data", fetch_data)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("generate_answer", generate_answer)
    
    # Define edges
    workflow.set_entry_point("detect_intent")
    workflow.add_edge("detect_intent", "fetch_data")
    workflow.add_edge("fetch_data", "analyze_data")
    workflow.add_edge("analyze_data", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    return workflow.compile()


# Global workflow instance
_workflow = None


def get_workflow():
    """Get or create workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow
