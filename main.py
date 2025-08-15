
#from langchain_core import 
from langchain_core.pydantic_v1 import BaseModel, Field

from langgraph.graph import Graph
from typing import Dict, Any, TypedDict

class AgentState(TypedDict):
    
    current_node: str
    memory: dict

class AgState(BaseModel):
    first: str = Field(..., default="default_value")
    second: int = Field(..., default=0)
    third: float = Field(..., default=0.0)
    



#---------------------- nodes -------------------------

workflow.add_node(