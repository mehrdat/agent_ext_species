from __future__ import annotations
from typing import Any, Dict, List
import os
import duckdb
from langchain_core.pydantic_v1 import BaseModel, Field

DUCK_PATH = os.getenv("DUCKDB_PATH", "data/db.duckdb")

class DBResults(BaseModel):
    taxon_id: int | None = None
    scientific_name: str | None = None
    common_names: List[str] = []
    taxonomy: Dict[str, Any] = {}
    assessment: Dict[str, Any] | None = None
    habitats: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []
    occurrence_count: int | None = None
    bbox: List[float] | None = None

class DBManagerOutput(BaseModel):
    db_results: DBResults = Field(default_factory=DBResults)
    retrieval_context: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


def _conn():
    os.makedirs(os.path.dirname(DUCK_PATH), exist_ok=True)
    return duckdb.connect(DUCK_PATH)


def db_manager_duckdb(state: Dict[str, Any]) -> DBManagerOutput:
    entities: List[str] = list(state.get("entities", []) or [])
    task = state.get("task")
    q = state.get("user_input", "")

    if not entities:
        return DBManagerOutput(warnings=["No entities provided to DB (duckdb)"])

    name = entities[0]
    con = _conn()
    try:
        taxon = con.execute(
            "SELECT taxon_id, scientific_name, common_names, kingdom, phylum, class, \"order\", family, genus FROM taxon WHERE lower(scientific_name)=lower(?) OR list_contains(common_names, ?) LIMIT 1",
            [name, name],
        ).fetchone()
        if not taxon:
            return DBManagerOutput(warnings=["Species not found in DuckDB"])
        (taxon_id, sci, commons, kingdom, phylum, clazz, order, family, genus) = taxon
        res = DBResults(
            taxon_id=taxon_id,
            scientific_name=sci,
            common_names=commons or [],
            taxonomy={"kingdom":kingdom,"phylum":phylum,"class":clazz,"order":order,"family":family,"genus":genus},
        )
        assess = con.execute("SELECT status, criteria, assessed_on, assessor, source, url, notes FROM assessment WHERE taxon_id=? ORDER BY assessed_on DESC NULLS LAST LIMIT 1", [taxon_id]).fetchone()
        if assess:
            (status, criteria, assessed_on, assessor, source, url, notes) = assess
            res.assessment = {"status":status, "criteria":criteria, "assessed_on":assessed_on, "assessor":assessor, "source":source, "url":url, "notes":notes}
        res.habitats = [dict(zip([c[0] for c in con.description], row)) for row in con.execute("SELECT habitat_type, importance, source FROM habitat WHERE taxon_id=? LIMIT 15", [taxon_id]).fetchall()] if con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='habitat'").fetchone() else []
        res.images = [
            {"title":row[1],"url":row[2],"thumbnail_url":row[3],"width":row[4],"height":row[5],"format":row[6],"license":row[7],"attribution":row[8],"source":row[9],"captured_on":row[10]}
            for row in con.execute("SELECT id, title, url, thumbnail_url, width, height, format, license, attribution, source, captured_on FROM image_asset WHERE taxon_id=? ORDER BY 1 DESC LIMIT 12", [taxon_id]).fetchall()
        ]
        # occurrence summary if lon/lat columns exist
        try:
            occ = con.execute("SELECT count(*), min(longitude), min(latitude), max(longitude), max(latitude) FROM occurrence WHERE taxon_id=?", [taxon_id]).fetchone()
            if occ and occ[0] is not None:
                res.occurrence_count = int(occ[0])
                res.bbox = [float(occ[1]), float(occ[2]), float(occ[3]), float(occ[4])]
        except Exception:
            pass
        # No vector search on DuckDB example; return empty RAG ctx
        return DBManagerOutput(db_results=res, retrieval_context=[], warnings=[])
    finally:
        con.close()


def db_manager_duckdb_node(state: Dict[str, Any]) -> Dict[str, Any]:
    out = db_manager_duckdb(state)
    patch = {"db_results": out.db_results.dict(), "retrieval_context": out.retrieval_context}
    if out.warnings:
        patch["warnings"] = (state.get("warnings") or []) + out.warnings
    return patch