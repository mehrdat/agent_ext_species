from typing import List, Optional, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
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

def _heuristic_entities(text: str) -> list[str]:
    """Lightweight species/entity extractor when LLM unavailable.
    - Capture binomials like 'Panthera leo' (Capital genus + lowercase epithet)
    - Deduplicate and keep order of appearance.
    """
    import re
    ents: list[str] = []
    seen = set()
    # Binomial pattern
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\s([a-z]{3,})\b", text):
        candidate = f"{m.group(1)} {m.group(2)}"
        if candidate not in seen:
            seen.add(candidate)
            ents.append(candidate)
    # If no binomials found, fall back to possible single-word genus names
    if not ents:
        STOP = {"Show","List","Give","Provide","Tell","Status","Images","Image","Recent","Latest","for","and"}
        for tok in re.findall(r"\b[A-Z][a-z]{3,}\b", text):
            if tok in STOP:
                continue
            if tok not in seen:
                seen.add(tok)
                ents.append(tok)
    # Normalize common ambiguous vernaculars to scientific genus (still ambiguous)
    NORMALIZE = {
        "Panther": "Panthera",  # colloquial shortening
        "panther": "Panthera",
    }
    ents = [NORMALIZE.get(e, e) for e in ents]
    return ents

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
    if not user_input or not str(user_input).strip():
        # Minimal default to let router send to DB or noop
        return InterpreterOutputMessages(
            user_input="",
            intent="lookup",
            entities=[],
            task="lookup",
            required_tools=["DBManager"],
            query_plan=["await user input"],
        )
    
    llm=get_llm()
    chain= (INTERPRETER_PROMPT.partial(format_instructions=parser.get_format_instructions())|llm|parser)
    
    try:
        result: InterpreterOutputMessages= chain.invoke({"user_input": user_input})
    except ValidationError:
        result = None
    except Exception:
        result = None
    # If model responded but no entities, apply heuristic augmentation
    if result and not result.entities:
        extra = _heuristic_entities(user_input)
        if extra:
            result.entities = extra
    if result is None:
        # Heuristic fallback
        ents = _heuristic_entities(user_input)
        result = InterpreterOutputMessages(
            user_input=user_input,
            intent="lookup",
            entities=ents,
            task="lookup",
            required_tools=["DBManager", "WebResearcher"],
            query_plan=[
                "parse species names (heuristic)",
                "query database for first species",
                "fetch external summary & images",
                "compose report",
            ],
        )
    return result

# def interpret_node(state: Dict[str, Any])-> Dict[str, Any]:
#     out=interpret(state)
#     new_state=dict(state)
#     new_state.update(out.dict())
#     return new_state
