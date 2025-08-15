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



class InterpreterMessages(BaseModel):
    user_input: str=Field(..., description="User input to be interpreted")
    #system_response: str
    intent: str | None = Field(..., description="Intent of the user input")
    entities: list[str] = Field(..., description="Entities extracted from the user input")
    task: str | None = Field(..., description="Task to be performed")
    required_tools: list[str] = Field(..., description="Tools required for the task")
    query_plan: list[str] = Field(..., description="Plan for querying data")

INTERPRETER = ChatPromptTemplate.from_messages([("system", "you are a helpful assistant to interprete the user input."),
                                        ("user", "{user_input}")])







