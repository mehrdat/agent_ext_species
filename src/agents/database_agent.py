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

import json
import re

from langchain_core.prompts import ChatPromptTemplate


class SearchQuery(TypedDict):
    search_query: str
    justification: str


prompt= ChatPromptTemplate.from_messages([("system", ""),
                                           ("user","{user_input}")])





