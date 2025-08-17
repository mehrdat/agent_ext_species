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
    patch.update(out.dict())
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
    # Route node writes key 'next_node' containing list of nodes to execute
    g.add_conditional_edges("QueryRouter", lambda s: s.get("next_node", []))
    g.add_edge("DBManager", "Reporter")
    g.add_edge("WebResearcher", "Reporter")
    g.add_edge("Reporter", END)
    return g.compile()


def bootstrap(initial: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return initial or {}