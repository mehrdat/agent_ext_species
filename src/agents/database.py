import os
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.pydantic_v1 import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import SQLAlchemyError
from __future__ import annotations



_DB_ENGINE:Optional[Engine] = None


def get_engine()->Engine:
    """Get the SQLAlchemy engine for database operations."""
    global _DB_ENGINE
    if _DB_ENGINE is None:
        db_url=os.environ.get("DB_URL")
        if not db_url:
            raise RuntimeError("DB_URL environment variable is not set.")
        _DB_ENGINE = create_engine(db_url, pool_pre_ping=True)
    return _DB_ENGINE


class DBResults(BaseModel):
    """Model to represent the results of a database query."""

    taxon_id:Optional[int]= None
    scientific_name:Optional[str]= None
    common_names:List[str]= []
    taxonomy:Dict[str,Optional[str]]= {}

    assessment:Optional[Dict[str, Any]] = None
    habitats:List[Dict[str, Any]]= []
    images:List[Dict[str, Any]]= []

    occurrence_count:Optional[int]= None
    bbox:Optional[List[float]]= None

class DBManagerOutput(BaseModel):
    """Model to represent the output of the DBManager."""

    db_results: DBResults=Field(default_factory=DBResults, description="Results from the database query")
    retrieval_context: List[Dict[str, Any]] = Field(default_factory=list, description="Context information for the retrieval")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during the retrieval process")
    

_SPECIES_SELECT = text(
    """
    SELECT taxon_id, scientific_name, common_names,
        kingdom, phylum, class, "order", family, genus
    FROM taxon
    WHERE lower(scientific_name) = lower(:q)
        OR (:q) = ANY(common_names)
    LIMIT 1
    """
)


_ASSESSMENT_SELECT = text(
    """
    SELECT status, criteria, assessed_on, assessor, source, url, notes
    FROM assessment WHERE taxon_id = :taxon_id
    ORDER BY assessed_on DESC NULLS LAST
    LIMIT 1
    """
)


_HABITAT_SELECT = text(
    """
    SELECT habitat_type, importance, source
    FROM habitat WHERE taxon_id = :taxon_id
    ORDER BY importance DESC NULLS LAST
    LIMIT :limit
    """
)


_IMAGES_SELECT = text(
    """
    SELECT id, title, url, thumbnail_url, width, height, format, license, attribution, source, captured_on
    FROM image_asset WHERE taxon_id = :taxon_id
    ORDER BY added_at DESC
    LIMIT :limit
    """
)


# Optional, only if PostGIS & occurrence table exist
_OCC_SUMMARY = text(
    """
    SELECT COUNT(*)::int AS n,
        MIN(ST_X(geom)) AS minlon, MIN(ST_Y(geom)) AS minlat,
        MAX(ST_X(geom)) AS maxlon, MAX(ST_Y(geom)) AS maxlat
    FROM occurrence WHERE taxon_id = :taxon_id
    """
)


# Vector search (pgvector) — adjust operator to your ops class (cosine/euclidean/inner)
_DOC_VECTOR_SEARCH = text(
    """
    SELECT id, text, source_url, source_id, license,
        1 - (embedding <=> :qvec) AS score
    FROM doc_chunk
    WHERE taxon_id = :taxon_id
    ORDER BY embedding <-> :qvec
    LIMIT :k
    """
)

# Fallback keyword search (very simple ILIKE; replace with tsquery if available)
_DOC_KEYWORD_SEARCH = text(
    """
    SELECT id, text, source_url, source_id, license,
        CASE WHEN text ILIKE :kw THEN 0.9 ELSE 0.5 END AS score
    FROM doc_chunk
    WHERE taxon_id = :taxon_id AND text ILIKE :kw
    ORDER BY id DESC
    LIMIT :k
    """
)

def _first_nonempty(xs:List[str])->Optional[str]:
    """Return the first non-empty string from a list, or None."""
    for x in xs:
        if isinstance(x, str) and x.strip():
            return x
    return None

def _extract_user_query(state:Dict[str, Any])->str:

    return (
        _first_nonempty([
            state.get("user_input"),
            state.get("query"),
            state.get("question"),
        ]) or ""
    )

def _resolve_species(engine:Engine,entities:List[str])->Optional[str,Any]:
    """Resolve a species name from the database."""
    if not entities:
        return None
    with engine.begin() as conn:
        for ent in entities:
            r:Result=conn.execute(
                _SPECIES_SELECT,
                {"q": ent}
            )
            row=r.mappings().first()
            if row:
                return dict(row)
    return None


def _fetch_profile(engine:Engine,taxon_id:int, want_occ:bool,img_limit:int=8)->DBResults:
    
    out=DBResults()
    with engine.begin() as conn:
        #assessment
        a=conn.execute(_ASSESSMENT_SELECT, {"taxon_id": taxon_id}).mappings().first()
        #habitats
        h=conn.execute(_HABITAT_SELECT, {"taxon_id": taxon_id, "limit": 15}).mappings().all()
        #images
        img=conn.execute(_IMAGES_SELECT, {"taxon_id": taxon_id, "limit": img_limit}).mappings().all()
        
        t=conn.execute(
            text(
                """
                SELECT scientific_name, common_names, kingdom, phylum, class, \"order\", family, genus,
                    from taxon WHERE taxon_id = :taxon_id
                """
            ),
            {"taxon_id": taxon_id}
        ).mappings().first()
        out.taxon_id=taxon_id
        
        if t:
            out.scientific_name=t.get("scientific_name")
            out.common_names=t.get("common_names") or []
            out.toxonomy={
                "kingdom": t.get("kingdom"),
                "phylum": t.get("phylum"),
                "class": t.get("class"),
                "order": t.get("order"),
                "family": t.get("family"),
                "genus": t.get("genus"),
            }
        if a:
            out.assessment=dict(a)
        if h:
            out.habitats=[dict(habitat) for habitat in h]
        if img:
            out.images=[dict(image) for image in img]
        
        if want_occ:
            try:
                occ=conn.execute(_OCC_SUMMARY, {"taxon_id": taxon_id}).mappings().first()
                if occ and occ.get("n") is not None:
                    out.occurrence_count=int(occ["n"])
                    out.bbox=[
                        float(occ["minlon"]),
                        float(occ["minlat"]),
                        float(occ["maxlon"]),
                        float(occ["maxlat"]),
                    ]
            except SQLAlchemyError as e:
                pass
    return out



def _vector_retrieve(engine:Engine,taxon_id:int,query_vec:List[float],k:int) -> List[Dict[str, Any]]:
    """Retrieve documents using vector search."""
    try:
        with engine.begin() as conn:
            rows=conn.execute(_DOC_VECTOR_SEARCH, {"taxon_id": taxon_id, "qvec": query_vec, "k": k}).mappings().all()
            return [dict(row) for row in rows]
    except SQLAlchemyError as e:
        return []
    


def _keyword_retrieve(engine:Engine,taxon_id:int,query:str,k:int) -> List[Dict[str, Any]]:
    """Retrieve documents using keyword search."""
    kw=f"%{query[:200]}%" if query else "%"
    with engine.begin() as conn:
        rows=conn.execute(_DOC_KEYWORD_SEARCH, {"taxon_id": taxon_id, "kw": kw, "k": k}).mappings().all()
        return [dict(row) for row in rows]


def db_manager(state:Dict[str, Any], *,embedder:Optional[Any]=None,retr_k:int=12)->DBManagerOutput:
    engine = get_engine()

    entities: List[str] = list(state.get("entities", []) or [])
    task: Optional[str] = state.get("task")
    user_query: str = _extract_user_query(state)

    warnings: List[str] = []

    db_ops = (state.get("db_ops") or "read").lower()
    if db_ops == "write":
        payload = state.get("write_payload") or {}
        write_kind = (payload.get("kind") or "").lower()
        if write_kind == "image_asset":
            out = _insert_image_asset(engine, payload)
            warnings.extend(out[1])
            return DBManagerOutput(db_results=DBResults(), retrieval_context=[], warnings=warnings)
        else:
            warnings.append("Unsupported write kind; no action taken.")
            return DBManagerOutput(db_results=DBResults(), retrieval_context=[], warnings=warnings)

    resolved = _resolve_species(engine, entities)
    if not resolved:
        return DBManagerOutput(
            db_results=DBResults(),
            retrieval_context=[],
            warnings=["No matching species found in DB for provided entities."],
        )

    taxon_id = int(resolved["taxon_id"])  # type: ignore

    want_occ = task in {"map", "trend", "report"}
    profile = _fetch_profile(engine, taxon_id, want_occ)

    ctx: List[Dict[str, Any]] = []
    if embedder is not None:
        try:
            qvec = embedder(user_query) if user_query else embedder(profile.scientific_name or "")
            if qvec is not None:
                vec_ctx = _vector_retrieve(engine, taxon_id, qvec, retr_k)
                ctx.extend(vec_ctx)
        except Exception:
            warnings.append("Vector retrieval failed; falling back to keyword.")
    if not ctx:  
        ctx = _keyword_retrieve(engine, taxon_id, user_query or (profile.scientific_name or ""), retr_k)

    return DBManagerOutput(db_results=profile, retrieval_context=ctx, warnings=warnings)



def _insert_image_asset(engine: Engine, payload: Dict[str, Any]) -> Tuple[Optional[int], List[str]]:
    warnings: List[str] = []
    required = ["taxon_id", "url", "license", "attribution"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        warnings.append(f"Missing required fields for image_asset: {', '.join(missing)}")
        return None, warnings

    ins = text(
        """
        INSERT INTO image_asset (taxon_id, title, url, thumbnail_url, width, height, format, license, attribution, source, captured_on)
        VALUES (:taxon_id, :title, :url, :thumbnail_url, :width, :height, :format, :license, :attribution, :source, :captured_on)
        RETURNING id
        """
    )
    params = {k: payload.get(k) for k in [
        "taxon_id", "title", "url", "thumbnail_url", "width", "height", "format", "license", "attribution", "source", "captured_on"
    ]}

    try:
        with get_engine().begin() as conn:
            rid = conn.execute(ins, params).scalar_one()
            return int(rid), warnings
    except SQLAlchemyError as e:
        warnings.append(f"Insert failed: {e}")
        return None, warnings

def db_manager_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        out = db_manager(state)
        patch: Dict[str, Any] = {
            "db_results": out.db_results.dict(),
            "retrieval_context": out.retrieval_context,
        }
        if out.warnings:
            warnings = list(state.get("warnings", []) or [])
            warnings.extend(out.warnings)
            patch["warnings"] = warnings
        return patch
    except Exception as e:
        errs = list(state.get("errors", []) or [])
        errs.append(f"DBManager error: {type(e).__name__}: {e}")
        return {"errors": errs}

