from typing import List, Literal, Annotated, Optional, Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field,ValidationError

from src.llm.llm_config import get_llm

TASK_HINT = "One of: lookup, compare, map, trend, image_gallery, report, write, other"
TOOLS_HINT = "Choose from: DBManager, WebResearcher, Reporter"

class RouterOutput(BaseModel):
    """Routing decision produced by the Query Router node.
    """
    user_input: str = Field(..., description="Original user input text")
    intent: Optional[str] = Field(None, description="Interpreter's inferred intent")
    entities: List[str] = Field(default_factory=list, description="Entities extracted by Interpreter")
    task: Optional[str] = Field(None, description="Task label from Interpreter (lookup/compare/map/trend/image_gallery/report/write/other)")

    # Router decisions
    next_node: List[str] = Field(default_factory=list,description='Ordered list of next nodes to execute (e.g., ["DBManager","WebResearcher"])')
    rout_decision:str= Field("", description="Routing decision (DBagent or WebSearchAgent)")
    reasons:List[str] = Field(default_factory=list, description="Short bullet reasons for the routing choice")


_DEF_IMAGE_WORDS={
    "image", "images", "photo", "photos", "picture", "pictures", "gallery", "illustration"
}

_DEF_LATEST_WORDS={
    "latest", "recent", "update", "updated", "newest"
}



def _extract_user_input(state: Any) -> str:
    if isinstance(state,dict):
        for k in ("user_input", "input", "query", "question", "text"):
            val=state.get(k)
            if isinstance(val, str) and val.strip():
                return val
            
        return ""
    val=getattr(state, "user_input", None)
    if isinstance(val, str) and val.strip():
        return val
    return str(state)


def _get(state:Any, key: str, default:Any=None) -> Any:
    """Helper to extract a value from state, supporting both dict and object access."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)



#parser = PydanticOutputParser(pydantic_object=RouterOutputMessages)

def route(state:Any)-> RouterOutput:
    """Decide which nodes to run next based on the Interpreter output + light heuristics.

    Inputs expected in `state` (from your Interpreter):
    - user_input: str
    - intent: Optional[str]
    - entities: List[str]
    - task: Optional[str]
    - required_tools: Optional[List[str]]
    - image_candidates: Optional[List[dict]] (if already available)

    Output:
    - RouterOutput with `next_nodes` and `route_decision`.
    """
    user_input=_extract_user_input(state)

