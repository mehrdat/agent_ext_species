from __future__ import annotations
from langgraph.graph import StateGraph, END
from typing import Any, Dict

from interpreter_agent_fixed import interpret_node   # from your canvas file
from router_agent import route_node                  # from your canvas file
from db_agent import db_manager_node                 # Postgres path
from src.agents.db_duckdb_agent import db_manager_duckdb_node  # HF path
from src.agents.web_researcher import web_researcher_node
from src.agents.reporter_agent import reporter_node

import os

class State(dict):
    pass


def build_graph() -> Any:
    g = StateGraph(State)
    g.add_node("Interpreter", interpret_node)
    g.add_node("QueryRouter", route_node)

    # Choose DB backend by env
    backend = os.getenv("DB_BACKEND", "postgres").lower()
    if backend == "duckdb":
        g.add_node("DBManager", db_manager_duckdb_node)
    else:
        g.add_node("DBManager", db_manager_node)

    g.add_node("WebResearcher", web_researcher_node)
    g.add_node("Reporter", reporter_node)

    g.set_entry_point("Interpreter")
    g.add_edge("Interpreter", "QueryRouter")
    g.add_conditional_edges("QueryRouter", lambda s: s.get("next_nodes", []))
    g.add_edge("DBManager", "Reporter")
    g.add_edge("WebResearcher", "Reporter")
    g.add_edge("Reporter", END)
    return g.compile()


def bootstrap(initial: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return initial or {}