

from typing import Dict, List, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.pydantic_v1 import BaseModel, Field

"""
SpeciesAssessmentOutput (extends base) (only for extinction/risk agent)

species_name: str
scientific_name: str
status: Literal["CR","EN","VU","NT","LC","DD","EX","EW"]
primary_threats: List[str]
recommended_actions: List[str]
urgency_score: float (0–1)
sources: List[str]
uncertainties: Optional[List[str]]
data_quality: Literal["high","medium","low"]

"""

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


class BaseAgentOutput(BaseModel):
    agent: str = Field(..., description="The name of the agent that generated the output")
    reasoning: str = Field(..., description="The reasoning behind the output")
    confidence_score: float = Field(..., description="The confidence score of the output (0-1)")
    next_steps: List[str] = Field(..., description="The next steps to take based on the output")


class InterpreterOutput(BaseAgentOutput):
    intent: Literal["identify_species", "assess_extinction_risk", "request_conservation_actions", "compare_regions"]
    required_info: List[str] 
    extracted_entities: Dict[str, str]
    ambiguity_notes: Optional[str]
    route: List[str]
    missing: bool


class SpeciesAssessmentOutput(BaseAgentOutput):
    species: str = Field(..., description="The species being assessed")
    habitat: str = Field(..., description="The habitat of the species")
    population_estimate: int = Field(..., description="The estimated population of the species")
    conservation_status: str = Field(..., description="The conservation status of the species")


