"""Utilities for using heavy datasets hosted on Hugging Face Datasets."""
from __future__ import annotations
import os
from typing import Dict, Any
from datasets import load_dataset
import duckdb

# Expected dataset contains parquet splits or tables named: taxon, assessment, habitat, image_asset, doc_chunk, occurrence

HF_DATASET = os.getenv("HF_DATASET_REPO")  # e.g., "username/under-threat-species"
DUCK_PATH = os.getenv("DUCKDB_PATH", "data/db.duckdb")

SCHEMA_TABLES = ["taxon", "assessment", "habitat", "image_asset", "doc_chunk", "occurrence"]


def build_duckdb_from_hf() -> str:
    if not HF_DATASET:
        raise RuntimeError("HF_DATASET_REPO not set")
    con = duckdb.connect(DUCK_PATH)
    for table in SCHEMA_TABLES:
        try:
            ds = load_dataset(HF_DATASET, table, split="train", streaming=True)
        except Exception:
            # allow missing tables
            continue
        # stream into DuckDB using copy from iterator
        # Create table if not exists by sampling first 100 rows into a temp view
        sample = []
        for i, row in enumerate(ds):
            sample.append(row)
            if i >= 100: break
        if not sample:
            continue
        con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM read_json_auto(?) LIMIT 0", [sample])
        # Insert all rows
        con.execute(f"INSERT INTO {table} SELECT * FROM read_json_auto(?)", [sample])
        # Continue streaming the rest
        for row in ds.skip(len(sample)):
            con.execute(f"INSERT INTO {table} SELECT * FROM read_json_auto(?)", [[row]])
    con.close()
    return DUCK_PATH