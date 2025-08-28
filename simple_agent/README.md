# Simple Species Lookup Agent

A minimal script that:
1. Connects to DuckDB (path via `DUCKDB_PATH` env or `data/db.duckdb`).
2. Ensures minimal schema + seed (lion & tiger) if missing.
3. Accepts a user query (species binomial or genus) from CLI.
4. Prints a concise JSON result (basic taxonomy, status, images count).

## Run
```bash
export DUCKDB_PATH=data/db.duckdb  # optional
python simple_agent/main.py "Panthera leo"
```
If you pass only a genus (e.g. `Panthera`) it will list available species suggestions.
