from typing import List, Literal, Annotated, Optional, Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field,ValidationError

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
    if not user_input:
        raise ValueError("user_input is required")

    intent: Optional[str] = _get(state, "intent")
    entities: List[str] = list(_get(state, "entities", []) or [])
    task:Optional[str] = _get(state, "task")
    required_tools:List[str] = list(_get(state, "required_tools", []) or [])

    user_lc = user_input.lower()
    species_present=len(entities)>0
    
    image_candidates=_get(state, "image_candidates", [])
    have_images = len(image_candidates) > 0
    
    wants_images=(
        task == "image_gallery" or any (word in user_lc for word in _DEF_IMAGE_WORDS)
        
    )
    wants_latest= any(word in user_lc for word in _DEF_LATEST_WORDS)

    write_request= (task=="write") or ("upload" in user_lc ) or ("add" in user_lc and "image" in user_lc)
    
    next_nodes: List[str] = []
    reasons: List[str] = []
    
    if write_request:
        next_nodes.append("DBManager")
        reasons.append("User requested a write/update operation.")
        
    else:
        if species_present or task in ("lookup", "compare", "map", "trend","report"):
            next_nodes.append("DBManager")
            if species_present:
                reasons.append("Species/entities present → fetch canonical data from DB.")
            else:
                reasons.append("Task requires structured data (lookup/compare/map/trend/report).")

        need_web = wants_images and not have_images
        need_web = wants_latest or need_web
        need_web = need_web or ("WebResearcher" in required_tools)
        need_web = need_web or (not species_present)

        if need_web:
            if not next_nodes and not species_present:
                next_nodes.append("WebResearcher")
                reasons.append("No species recognized → use web to identify/clarify.")
            else:
                next_nodes.append("WebResearcher")
                if wants_images and not have_images:
                    reasons.append("Need images → use WebResearcher with license filters.")
                if wants_latest:
                    reasons.append("User asked for recent/updated info → include WebResearcher.")
                if "WebResearcher" in required_tools:
                    reasons.append("Interpreter requested WebResearcher.")

    seen = set()
    dedup_next = []
    
    for n in next_nodes:
        if n not in seen:
            dedup_next.append(n)
            seen.add(n)

    decision = " -> ".join(dedup_next) if dedup_next else "(no-op)"
    return RouterOutput(
        user_input=user_input,
        intent=intent,
        entities=entities,
        task=task,
        next_node=dedup_next,
        rout_decision=decision,
        reasons=reasons
    )
    
    
def route_node(state:Dict[str,Any])-> Dict[str, Any]:

    out = route(state)
    new_state = dict(state)
    new_state["next_node"] = out.next_node
    new_state["route_decision"] = out.route_decision
    new_state["reasons"] = out.reasons
    new_state["intent"] = out.intent
    new_state["entities"] = out.entities
    new_state["task"] = out.task

    return new_state

