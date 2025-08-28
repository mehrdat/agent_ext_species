#!/usr/bin/env python
"""Minimal species lookup against DuckDB.

Usage:
  python -m simple_agent.main "Panthera leo"
  python simple_agent/main.py Panthera

Environment:
  DUCKDB_PATH (default data/db.duckdb)
  SIMPLE_AUTO_INIT=1 to create schema/seed if missing.
"""
from __future__ import annotations
import os
import sys
import json
from typing import Any, Dict, List
import duckdb

DB_PATH = os.getenv("DUCKDB_PATH", "data/db.duckdb")
AUTO_INIT = os.getenv("SIMPLE_AUTO_INIT", "1") == "1"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS taxon (
        taxon_id INTEGER PRIMARY KEY,
        scientific_name TEXT UNIQUE,
        common_names TEXT[],
        kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT,
        family TEXT, genus TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS assessment (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER,
        status TEXT,
        criteria TEXT,
        assessed_on DATE,
        assessor TEXT,
        source TEXT,
        url TEXT,
        notes TEXT
    );""",
]
SEED = [
    """INSERT OR IGNORE INTO taxon (taxon_id, scientific_name, common_names, kingdom, phylum, class, "order", family, genus) VALUES
    (1,'Panthera leo', ['lion'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera'),
    (2,'Panthera tigris', ['tiger'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera');""",
    """INSERT OR IGNORE INTO assessment (id,taxon_id,status,criteria,assessed_on,assessor,source,url,notes) VALUES
    (1,1,'Vulnerable','A2','2023-12-01','IUCN','IUCN','https://www.iucnredlist.org/','Population declining'),
    (2,2,'Endangered','A2','2023-11-15','IUCN','IUCN','https://www.iucnredlist.org/','Habitat loss');""",
]

def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)

def ensure_schema(con):
    if not AUTO_INIT:
        return
    for stmt in SCHEMA:
        con.execute(stmt)
    for stmt in SEED:
        con.execute(stmt)

def lookup(term: str) -> Dict[str, Any]:
    term = term.strip()
    con = conn()
    try:
        ensure_schema(con)
        row = con.execute("SELECT taxon_id, scientific_name, common_names, kingdom, phylum, class, \"order\", family, genus FROM taxon WHERE lower(scientific_name)=lower(?)", [term]).fetchone()
        if row:
            (tid,sci,commons,kingdom,phylum,clazz,order,family,genus)=row
            assess = con.execute("SELECT status, criteria, assessed_on FROM assessment WHERE taxon_id=? ORDER BY assessed_on DESC NULLS LAST LIMIT 1", [tid]).fetchone()
            return {
                "match_type":"species",
                "scientific_name": sci,
                "common_names": commons or [],
                "taxonomy": {"kingdom":kingdom,"phylum":phylum,"class":clazz,"order":order,"family":family,"genus":genus},
                "status": assess[0] if assess else None,
                "criteria": assess[1] if assess else None,
                "assessed_on": assess[2] if assess else None,
            }
        # Try genus suggestions
        genus_rows = con.execute("SELECT scientific_name FROM taxon WHERE lower(genus)=lower(?) LIMIT 25", [term]).fetchall()
        if genus_rows:
            return {
                "match_type":"genus",
                "genus": term,
                "species_suggestions": [r[0] for r in genus_rows]
            }
        return {"match_type":"none","query": term, "message":"No match in database"}
    finally:
        con.close()


def main(argv: List[str]):
    if len(argv) < 2:
        print("Provide a species binomial or genus, e.g. 'Panthera leo'", file=sys.stderr)
        return 1
    term = " ".join(argv[1:])
    result = lookup(term)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
