from __future__ import annotations
from langgraph.graph import StateGraph, END
from typing import Any, Dict

# Local agent node functions
from src.agents.interpreter import interpret as _interpret
from src.agents.query_router import route_node
from src.agents.db_duckdb_agent import db_manager_duckdb_node  # DuckDB backend (default here)
from src.agents.web_researcher import web_researcher_node
from src.agents.reporter_agent import reporter_node

class State(dict):
    pass


def _interpreter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper to adapt InterpreterOutputMessages to state dict patch."""
    out = _interpret(state)
    patch = state.copy()
    try:
        data = out.model_dump()
    except Exception:
        data = getattr(out, 'dict', lambda : {})()
    patch.update(data)
    # Ensure routing key present to avoid None path
    patch.setdefault("next_node", [])
    return patch


def build_graph() -> Any:
    g = StateGraph(State)
    g.add_node("Interpreter", _interpreter_node)
    g.add_node("QueryRouter", route_node)

    # Currently only DuckDB manager implemented; placeholder for future Postgres.
    g.add_node("DBManager", db_manager_duckdb_node)

    g.add_node("WebResearcher", web_researcher_node)
    g.add_node("Reporter", reporter_node)

    g.set_entry_point("Interpreter")
    g.add_edge("Interpreter", "QueryRouter")
    # Simplify: linear pipeline QueryRouter -> DBManager -> WebResearcher -> Reporter
    # Each downstream node will check if it was selected in state['next_node'] and no-op otherwise.
    g.add_edge("QueryRouter", "DBManager")
    g.add_edge("DBManager", "WebResearcher")
    g.add_edge("WebResearcher", "Reporter")
    g.add_edge("Reporter", END)
    return g.compile()


def bootstrap(initial: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return initial or {}


def run_pipeline(user_input: str, initial_state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Fallback sequential execution that mimics the intended graph.
    This is used because the current LangGraph compiled graph returns None (under investigation).
    """
    state: Dict[str, Any] = initial_state.copy() if initial_state else {}
    state["user_input"] = user_input
    # Interpreter
    interp = _interpret(state)
    try:
        data = interp.model_dump()
    except Exception:
        data = getattr(interp, 'dict', lambda : {})()
    state.update(data)
    # Router
    state = route_node(state)
    sel = state.get("next_node", []) or []
    # DB
    if (not sel) or ("DBManager" in sel):
        db_patch = db_manager_duckdb_node(state)
        state.update(db_patch)
    # Web
    if "WebResearcher" in sel:
        web_patch = web_researcher_node(state)
        state.update(web_patch)
    # Reporter always
    rep_patch = reporter_node(state)
    state.update(rep_patch)
    return state


def execute_graph(compiled, state: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility executor: some langgraph versions return None for invoke.
    We simulate execution by calling nodes sequentially using a linear path matching build_graph.
    """
    # If invoke works (returns dict), just use it
    try:
        out = compiled.invoke(state)
        if isinstance(out, dict) and out:
            return out
    except Exception:
        pass
    # Fallback linear path identical to run_pipeline but using existing state
    return run_pipeline(state.get("user_input", ""), state)