"""Utility script to initialize (or patch) the DuckDB database schema.
Creates tables if they do not already exist. Safe to re-run.

Usage (from project root):

    python -m src.scripts.init_duckdb --path data/db.duckdb

Environment: DUCKDB_PATH overrides --path.
"""
from __future__ import annotations
import duckdb
import argparse
import os

DEFAULT_PATH = "data/db.duckdb"

SCHEMA_SQL = [
    # Core taxon table
    """
    CREATE TABLE IF NOT EXISTS taxon (
        taxon_id INTEGER PRIMARY KEY,
        scientific_name TEXT UNIQUE,
        common_names TEXT[],
        kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT,
        family TEXT, genus TEXT
    );
    """,
    # Assessment (IUCN-like)
    """
    CREATE TABLE IF NOT EXISTS assessment (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER REFERENCES taxon(taxon_id),
        status TEXT,
        criteria TEXT,
        assessed_on DATE,
        assessor TEXT,
        source TEXT,
        url TEXT,
        notes TEXT
    );
    """,
    # Habitat info
    """
    CREATE TABLE IF NOT EXISTS habitat (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER REFERENCES taxon(taxon_id),
        habitat_type TEXT,
        importance TEXT,
        source TEXT
    );
    """,
    # Images (locally curated)
    """
    CREATE TABLE IF NOT EXISTS image_asset (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER REFERENCES taxon(taxon_id),
        title TEXT,
        url TEXT,
        thumbnail_url TEXT,
        width INTEGER,
        height INTEGER,
        format TEXT,
        license TEXT,
        attribution TEXT,
        source TEXT,
        captured_on DATE
    );
    """,
    # Occurrence points
    """
    CREATE TABLE IF NOT EXISTS occurrence (
        id INTEGER PRIMARY KEY,
        taxon_id INTEGER REFERENCES taxon(taxon_id),
        longitude DOUBLE,
        latitude DOUBLE,
        observed_on DATE,
        source TEXT
    );
    """,
]

SEED_SQL = [
    # Seed minimal example entries so UI shows something without external calls
    """
    INSERT OR IGNORE INTO taxon (taxon_id, scientific_name, common_names, kingdom, phylum, class, "order", family, genus)
    VALUES
      (1,'Panthera leo', ['lion'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera'),
      (2,'Panthera tigris', ['tiger'], 'Animalia','Chordata','Mammalia','Carnivora','Felidae','Panthera');
    """,
    """
    INSERT OR IGNORE INTO assessment (id, taxon_id, status, criteria, assessed_on, assessor, source, url, notes)
    VALUES
      (1,1,'Vulnerable','A2','2023-12-01','IUCN','IUCN','https://www.iucnredlist.org/','Population declining'),
      (2,2,'Endangered','A2','2023-11-15','IUCN','IUCN','https://www.iucnredlist.org/','Habitat loss');
    """,
]

def init_db(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = duckdb.connect(path)
    try:
        for stmt in SCHEMA_SQL:
            con.execute(stmt)
        for stmt in SEED_SQL:
            con.execute(stmt)
        return path
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=DEFAULT_PATH, help="DuckDB file path")
    args = parser.parse_args()
    path = os.getenv("DUCKDB_PATH", args.path)
    out = init_db(path)
    print("DuckDB initialized at", out)

if __name__ == "__main__":
    main()
