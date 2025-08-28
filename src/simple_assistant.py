"""Simple species assistant (minimal version).

Usage CLI:
    python -m src.simple_assistant "Panthera leo status"

Environment:
    DUCKDB_PATH (optional) path to DuckDB file (will be auto-created with seed rows if missing)

Design:
    1. Extract species (binomial or genus) with a regex.
    2. Query DuckDB for matching scientific_name or common_names.
    3. If not found and a genus given, list up to a few species suggestions.
    4. Fetch a short Wikipedia summary (best effort) if scientific name resolved.
"""
from __future__ import annotations
import os
import re
import sys
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

try:
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover
    duckdb = None  # type: ignore

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

DUCK_PATH = os.getenv("DUCKDB_PATH", "data/db.duckdb")

BINOMIAL_RE = re.compile(r"\b([A-Z][a-z]{2,})\s([a-z]{3,})\b")
GENUS_RE = re.compile(r"\b([A-Z][a-z]{3,})\b")
STOP = {"Status","Images","Image","Show","List","Give","Provide","Recent","Latest","for","and","about"}

@dataclass
class SimpleResult:
    query: str
    extracted: List[str]
    matched_scientific_name: str | None = None
    common_names: List[str] | None = None
    taxonomy: Dict[str, Any] | None = None
    assessment: Dict[str, Any] | None = None
    suggestions: List[str] | None = None
    summary: str | None = None
    warnings: List[str] | None = None


def _ensure_duck_schema(con):
    con.execute("""
    CREATE TABLE IF NOT EXISTS taxon (
        taxon_id INTEGER PRIMARY KEY,
        scientific_name TEXT UNIQUE,
        common_names TEXT[],
        kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT,
        family TEXT, genus TEXT
    );
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS assessment (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER,
        status TEXT, criteria TEXT, assessed_on DATE,
        assessor TEXT, source TEXT, url TEXT, notes TEXT
    );
    """)
    # Seed a couple if empty
    cnt = con.execute("SELECT count(*) FROM taxon").fetchone()[0]
    if cnt == 0:
        con.execute("""
        INSERT INTO taxon VALUES
          (1,'Panthera leo',['lion'],'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera'),
          (2,'Panthera tigris',['tiger'],'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera');
        """)
        con.execute("""
        INSERT INTO assessment VALUES
          (1,1,'Vulnerable','A2','2023-12-01','IUCN','IUCN','https://www.iucnredlist.org/','Population declining'),
          (2,2,'Endangered','A2','2023-11-15','IUCN','IUCN','https://www.iucnredlist.org/','Habitat loss');
        """)


def extract_entities(text: str) -> List[str]:
    ents = []
    seen = set()
    for m in BINOMIAL_RE.finditer(text):
        val = f"{m.group(1)} {m.group(2)}"
        if val not in seen:
            seen.add(val)
            ents.append(val)
    if not ents:
        for m in GENUS_RE.finditer(text):
            val = m.group(1)
            if val in STOP:
                continue
            if val not in seen:
                seen.add(val)
                ents.append(val)
    # normalize common ambiguous
    norm_map = {"Panther": "Panthera"}
    ents = [norm_map.get(e, e) for e in ents]
    return ents


def wiki_summary(name: str) -> str | None:
    if not requests:
        return None
    try:
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ','%20')}", timeout=8, headers={"User-Agent":"simple-bio-assistant/0.1"})
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("extract")
    except Exception:
        return None


def query_db(name: str, con) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT taxon_id, scientific_name, common_names, kingdom, phylum, class, \"order\", family, genus FROM taxon WHERE lower(scientific_name)=lower(?) OR list_contains(common_names, ?) LIMIT 1",
        [name, name]
    ).fetchone()
    if not row:
        return None
    (taxon_id, sci, commons, kingdom, phylum, clazz, order, family, genus) = row
    assess = con.execute(
        "SELECT status, criteria, assessed_on, assessor, source, url, notes FROM assessment WHERE taxon_id=? ORDER BY assessed_on DESC NULLS LAST LIMIT 1",
        [taxon_id]
    ).fetchone()
    assessment = None
    if assess:
        (status, criteria, assessed_on, assessor, source, url, notes) = assess
        assessment = {"status":status,"criteria":criteria,"assessed_on":assessed_on,"assessor":assessor,"source":source,"url":url,"notes":notes}
    return {
        'scientific_name': sci,
        'common_names': commons or [],
        'taxonomy': {"kingdom":kingdom,"phylum":phylum,"class":clazz,"order":order,"family":family,"genus":genus},
        'assessment': assessment
    }


def answer(question: str) -> SimpleResult:
    warnings: List[str] = []
    ents = extract_entities(question)
    if duckdb is None:
        warnings.append("duckdb not installed; DB step skipped")
        data = None
    else:
        os.makedirs(os.path.dirname(DUCK_PATH), exist_ok=True)
        con = duckdb.connect(DUCK_PATH)
        try:
            _ensure_duck_schema(con)
            data = None
            suggestions = []
            for cand in ents[:3]:
                data = query_db(cand, con)
                if data:
                    break
            if not data and ents:
                # genus suggestions
                genus = ents[0].split()[0]
                rows = con.execute("SELECT scientific_name FROM taxon WHERE lower(genus)=lower(?) LIMIT 6", [genus]).fetchall()
                suggestions = [r[0] for r in rows]
            summary = wiki_summary(data['scientific_name'] if data else ents[0] if ents else question)
            return SimpleResult(
                query=question,
                extracted=ents,
                matched_scientific_name=data.get('scientific_name') if data else None,
                common_names=data.get('common_names') if data else None,
                taxonomy=data.get('taxonomy') if data else None,
                assessment=data.get('assessment') if data else None,
                suggestions=suggestions or None,
                summary=summary,
                warnings=warnings or None,
            )
        finally:
            con.close()
    # no DB path
    summary = wiki_summary(ents[0]) if ents else None
    return SimpleResult(query=question, extracted=ents, summary=summary, warnings=warnings or None)


def format_markdown(res: SimpleResult) -> str:
    sci = res.matched_scientific_name or (res.extracted[0] if res.extracted else 'Unknown')
    lines = [f"# {sci} — {res.assessment.get('status') if res.assessment else 'Unknown'}"]
    commons = ", ".join(res.common_names or [])
    lines.append(f"**Common names**: {commons or '—'}\n")
    if res.summary:
        lines.append(res.summary)
    if res.taxonomy:
        t = res.taxonomy
        lines.append("\n## Taxonomy")
        lines.append(" · ".join([
            f"Kingdom: {t.get('kingdom','—')}",
            f"Phylum: {t.get('phylum','—')}",
            f"Class: {t.get('class','—')}",
            f"Order: {t.get('order','—')}",
            f"Family: {t.get('family','—')}",
            f"Genus: {t.get('genus','—')}"
        ]))
    if res.suggestions:
        lines.append("\n## Suggestions")
        for s in res.suggestions:
            lines.append(f"- {s}")
    if res.warnings:
        lines.append("\n## Warnings")
        for w in res.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


def main(argv: list[str]):
    if not argv:
        print("Provide a query, e.g. 'Panthera leo status'")
        return 1
    q = " ".join(argv)
    res = answer(q)
    print(json.dumps(asdict(res), indent=2, default=str))
    print("\n--- Markdown ---\n")
    print(format_markdown(res))
    return 0

if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
