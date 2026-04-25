from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.graph.nodes import detect_intent, select_sources, fetch_data, validate_data, analyze_data, generate_answer

def _needs_data(state: AgentState) -> str:
    intent = state.get("intent")
    if not intent:
        return "answer"
    if any([intent.daily_price_params, intent.variety_price_params, intent.production_params, intent.weather_params]):
        return "fetch"
    return "answer"

def _has_data(state: AgentState) -> str:
    return "analyze" if sum(len(v) for v in state.get("raw_data", {}).values()) > 0 else "answer"

def create_workflow():
    g = StateGraph(AgentState)
    g.add_node("detect_intent", detect_intent)
    g.add_node("select_sources", select_sources)
    g.add_node("fetch_data", fetch_data)
    g.add_node("validate_data", validate_data)
    g.add_node("analyze_data", analyze_data)
    g.add_node("generate_answer", generate_answer)
    g.set_entry_point("detect_intent")
    g.add_conditional_edges("detect_intent", _needs_data, {"fetch": "select_sources", "answer": "generate_answer"})
    g.add_edge("select_sources", "fetch_data")
    g.add_edge("fetch_data", "validate_data")
    g.add_conditional_edges("validate_data", _has_data, {"analyze": "analyze_data", "answer": "generate_answer"})
    g.add_edge("analyze_data", "generate_answer")
    g.add_edge("generate_answer", END)
    return g.compile()

_workflow = None

def get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = create_workflow()
    return _workflow
