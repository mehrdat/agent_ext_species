from typing import List, Literal, Annotated, Optional, Any

from typing_extensions import TypedDict
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from langgraph.graph import StateGraph, START,END

from langgraph.graph.message import add_messages

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.runnables import RunnableLambda
#from langchain_core.pydantic_v1 import 
#from pydantic import BaseModel, Field
from langchain_core.pydantic_v1 import BaseModel, Field

from langgraph.graph import StateGraph, END, START, Graph
from langgraph.checkpoint.sqlite import SqliteSaver 



memory=SqliteSaver.from_conn_string(":memory:")

class State(BaseModel):
    user_query: str
    intent: str | None = None
    entities: dict = {}
    task: str | None = None
    required_tools: list[str] = []
    query_plan: list[str] = []

    route_decision: str | None = None
    next_nodes: list[str] = []

    db_results: dict = {}
    retrieval_context: list[dict] = []  # chunks with source, score

    web_findings: list[dict] = []       # {text, url, source, date, license}
    image_candidates: list[dict] = []   # {url, license, title, width, height}

    ui_model: dict | None = None
    markdown_report: str | None = None
    pdf_bytes_b64: str | None = None

    errors: list[str] = []
    trace: list[str] = []

class ExtGraph(Graph):
    def __init__(self, state: State):
        super().__init__(state)
        self.app = None
        self.nodes_init()
        self.state = state
        
    def nodes_init(self):
        graph=StateGraph(State)
        graph.add_node("Interpreter", interpret)
        graph.add_node("QueryRouter", route)
        graph.add_node("DBManager", db_manager)
        graph.add_node("WebResearcher", web_research)
        graph.add_node("Reporter", reporter)
        graph.set_entry_point("Interpreter")
        graph.add_edge("Interpreter", "QueryRouter")

        graph.add_conditional_edges(
            "QueryRouter",
            lambda s: s.next_nodes,  # return list like ["DBManager", "WebResearcher"]
        )
        for n in ("DBManager", "WebResearcher"):
            graph.add_edge(n, "Reporter")
        graph.add_edge("Reporter", END)
        app=graph.compile(checkpointer=memory)

        self.app=app
        
        


