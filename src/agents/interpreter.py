from typing import List, Literal, Annotated, Optional, Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from pydantic import BaseModel, Field, ValidationError
from src.llm.llm_config import get_llm

TASK_HINT = "One of: lookup, compare, map, trend, image_gallery, report, write, other"
TOOLS_HINT = "Choose from: DBManager, WebResearcher, Reporter"

class InterpreterOutputMessages(BaseModel):
    """Normalized output for the Interpreter node.
    """
    user_input: str = Field(..., description="User input to be interpreted")
    intent: Optional[str] = Field(None, description="Short phrase for what the user wants")
    entities: List[str] = Field(default_factory=list, description="Key entities: species (scientific if possible), locations, dates")
    task: Optional[str] = Field(None, description=f"Task type. {TASK_HINT}")
    required_tools: List[str] = Field(default_factory=list, description=f"Tools that should be used next. {TOOLS_HINT}")
    query_plan: List[str] = Field(default_factory=list, description="2–5 high‑level steps to complete the request")



SYSTEM_PROMPT = (
    "You are the Interpreter for a biodiversity assistant.\n"
    "Extract the user's intent, entities (species in scientific names when possible,"
    " plus locations/time), task type, required tools, and a short query plan.\n\n"
    "Return ONLY JSON that matches the schema.\n\n{format_instructions}"
)

INTERPRETER_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("user", "{user_input}"),
    ]
)

parser = PydanticOutputParser(pydantic_object=InterpreterOutputMessages)

def _extract_user_input(state: Any) -> str:
    if isinstance(state,dict):
        for k in ("user_input", "input", "query", "question", "text"):
            val=state.get(k)
            if isinstance(val, str) and val.strip():
                return val
            
        return ""
    ui=getattr(state, "user_input", None)
    if isinstance(ui, str) and ui.strip():
        return ui
    return str(state)


def interpret(state: Any) -> InterpreterOutputMessages:
    """LangGraph node: interpret user input and produce a normalized structure.
    Accepts any `state` that contains a `user_input` string (directly or under
    common aliases). Returns an `InterpreterOutputMessages` instance.
    """
    user_input=_extract_user_input(state)
    if not user_input:
        raise ValueError("interpret() requires 'user_input' in the state.")
    
    llm=get_llm()
    chain= (INTERPRETER_PROMPT.partial(format_instructions=parser.get_format_instructions())|llm|parser)
    
    try:
        result: InterpreterOutputMessages= chain.invoke({"user_input": user_input})

    except ValidationError as e:
        result=InterpreterOutputMessages(
            user_input=user_input,
            intent="lookup",
            entities=[],
            task="lookup",
            required_tools=["DBManager"],
            query_plan=["identify species terms",
                        "query the database by scientific/common names",
                        "return a concise summary with citations"
                        ]
        )
    except ValidationError as e:
        raise RuntimeError(f"Interpretation failed: {type(e).__name__ : }: {e}")
    return result

# def interpret_node(state: Dict[str, Any])-> Dict[str, Any]:
#     out=interpret(state)
#     new_state=dict(state)
#     new_state.update(out.dict())
#     return new_state
