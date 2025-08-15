
#from langchain_core import 
from langchain_core.pydantic_v1 import BaseModel, Field

from langgraph.graph import Graph
from typing import Dict, Any, TypedDict



from .src.llm import get_llm
llm=get_llm()

