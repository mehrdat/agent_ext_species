from __future__ import annotations
from typing import Any, Dict, List
import os
import duckdb
from pydantic import BaseModel, Field

AUTO_INIT = os.getenv("AUTO_INIT_DUCK", "1") == "1"
AUTO_SEED = os.getenv("AUTO_SEED_DUCK", "1") == "1"

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
    species_suggestions: List[str] = Field(default_factory=list)


def _conn():
    os.makedirs(os.path.dirname(DUCK_PATH), exist_ok=True)
    return duckdb.connect(DUCK_PATH)

def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        return bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name=? LIMIT 1", [name]).fetchone())
    except Exception:
        return False

def _ensure_schema(con: duckdb.DuckDBPyConnection):
    if not AUTO_INIT:
        return
    created = []
    if not _table_exists(con, 'taxon'):
        con.execute("""
        CREATE TABLE taxon (
            taxon_id INTEGER PRIMARY KEY,
            scientific_name TEXT UNIQUE,
            common_names TEXT[],
            kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT,
            family TEXT, genus TEXT
        );
        """
        )
        created.append('taxon')
    if not _table_exists(con, 'assessment'):
        con.execute("""
        CREATE TABLE assessment (
            id INTEGER PRIMARY KEY,
            taxon_id INTEGER,
            status TEXT, criteria TEXT, assessed_on DATE,
            assessor TEXT, source TEXT, url TEXT, notes TEXT
        );
        """
        )
        created.append('assessment')
    # Only seed if just created taxon and AUTO_SEED
    if AUTO_SEED and ('taxon' in created):
        con.execute("""
            INSERT OR IGNORE INTO taxon (taxon_id, scientific_name, common_names, kingdom, phylum, class, "order", family, genus) VALUES
            (1,'Panthera leo', ['lion'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera'),
            (2,'Panthera tigris', ['tiger'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera');
        """)
        con.execute("""
            INSERT OR IGNORE INTO assessment (id, taxon_id, status, criteria, assessed_on, assessor, source, url, notes) VALUES
            (1,1,'Vulnerable','A2','2023-12-01','IUCN','IUCN','https://www.iucnredlist.org/','Population declining'),
            (2,2,'Endangered','A2','2023-11-15','IUCN','IUCN','https://www.iucnredlist.org/','Habitat loss');
        """)


def db_manager_duckdb(state: Dict[str, Any]) -> DBManagerOutput:
    entities: List[str] = list(state.get("entities", []) or [])
    # task = state.get("task")
    # q = state.get("user_input", "")

    if not entities:
        return DBManagerOutput(warnings=["No entities provided to DB (duckdb)"])

    name = entities[0]
    con = _conn()
    try:
        _ensure_schema(con)
        if not _table_exists(con, 'taxon'):
            return DBManagerOutput(warnings=["DuckDB: table 'taxon' not found – skipping DB lookup (web only)"])
        taxon = con.execute(
            "SELECT taxon_id, scientific_name, common_names, kingdom, phylum, class, \"order\", family, genus FROM taxon WHERE lower(scientific_name)=lower(?) OR list_contains(common_names, ?) LIMIT 1",
            [name, name],
        ).fetchone()
        suggestions: List[str] = []
        if not taxon:
            # Exact genus match suggestions
            genus_rows = con.execute(
                "SELECT scientific_name FROM taxon WHERE lower(genus)=lower(?) LIMIT 12",
                [name]
            ).fetchall()
            if genus_rows:
                suggestions = [r[0] for r in genus_rows]
                return DBManagerOutput(warnings=[f"Genus '{name}' provided; choose a species"], species_suggestions=suggestions)
            # Fuzzy genus (single char difference) suggestions
            all_rows = con.execute("SELECT DISTINCT genus FROM taxon").fetchall()
            def _lev(a: str, b: str) -> int:
                if abs(len(a) - len(b)) > 1:
                    return 99
                # simple edit distance <=1
                if a == b:
                    return 0
                if len(a) == len(b):
                    return sum(c1 != c2 for c1, c2 in zip(a, b))
                # insertion/deletion case
                long, short = (a, b) if len(a) > len(b) else (b, a)
                for i in range(len(long)):
                    if long[:i] + long[i+1:] == short:
                        return 1
                return 99
            fuzzy = [r[0] for r in all_rows if _lev(r[0].lower(), name.lower())<=1][:8]
            if fuzzy:
                # expand to species suggestions for first fuzzy genus
                species = []
                for gname in fuzzy:
                    rows = con.execute("SELECT scientific_name FROM taxon WHERE genus=? LIMIT 4", [gname]).fetchall()
                    species.extend(r[0] for r in rows)
                return DBManagerOutput(warnings=[f"Unmatched term '{name}'. Did you mean one of these genera?"], species_suggestions=species[:12])
            return DBManagerOutput(warnings=[f"Species or genus '{name}' not found in DuckDB"])
        (taxon_id, sci, commons, kingdom, phylum, clazz, order, family, genus) = taxon
        res = DBResults(
            taxon_id=taxon_id,
            scientific_name=sci,
            common_names=commons or [],
            taxonomy={"kingdom":kingdom,"phylum":phylum,"class":clazz,"order":order,"family":family,"genus":genus},
        )
        if _table_exists(con, 'assessment'):
            assess = con.execute("SELECT status, criteria, assessed_on, assessor, source, url, notes FROM assessment WHERE taxon_id=? ORDER BY assessed_on DESC NULLS LAST LIMIT 1", [taxon_id]).fetchone()
            if assess:
                (status, criteria, assessed_on, assessor, source, url, notes) = assess
                res.assessment = {"status":status, "criteria":criteria, "assessed_on":assessed_on, "assessor":assessor, "source":source, "url":url, "notes":notes}
        if _table_exists(con, 'habitat'):
            res.habitats = [
                dict(zip([c[0] for c in con.description], row))
                for row in con.execute("SELECT habitat_type, importance, source FROM habitat WHERE taxon_id=? LIMIT 15", [taxon_id]).fetchall()
            ]
        if _table_exists(con, 'image_asset'):
            res.images = [
                {"title":row[1],"url":row[2],"thumbnail_url":row[3],"width":row[4],"height":row[5],"format":row[6],"license":row[7],"attribution":row[8],"source":row[9],"captured_on":row[10]}
                for row in con.execute("SELECT id, title, url, thumbnail_url, width, height, format, license, attribution, source, captured_on FROM image_asset WHERE taxon_id=? ORDER BY 1 DESC LIMIT 12", [taxon_id]).fetchall()
            ]
        if _table_exists(con, 'occurrence'):
            try:
                occ = con.execute("SELECT count(*), min(longitude), min(latitude), max(longitude), max(latitude) FROM occurrence WHERE taxon_id=?", [taxon_id]).fetchone()
                if occ and occ[0] is not None:
                    res.occurrence_count = int(occ[0])
                    res.bbox = [float(occ[1]), float(occ[2]), float(occ[3]), float(occ[4])]
            except Exception:
                pass
        return DBManagerOutput(db_results=res, retrieval_context=[], warnings=[], species_suggestions=[])
    finally:
        con.close()


def db_manager_duckdb_node(state: Dict[str, Any]) -> Dict[str, Any]:
    # Skip if router did not select this node
    sel = state.get("next_node") or []
    if sel and "DBManager" not in sel:
        return {}
    out = db_manager_duckdb(state)
    try:
        db_results_payload = out.db_results.model_dump()
    except Exception:
        db_results_payload = out.db_results.dict()
    patch = {"db_results": db_results_payload, "retrieval_context": out.retrieval_context}
    if out.warnings:
        patch["warnings"] = (state.get("warnings") or []) + out.warnings
    if out.species_suggestions:
        patch["species_suggestions"] = out.species_suggestions
    return patch