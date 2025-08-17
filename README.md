# Under‑Threat Species — Multi‑Agent (LangGraph)

## Run locally with Ollama
export MODEL_PROVIDER=OLLAMA
export OLLAMA_MODEL=llama3:8b-instruct
export DB_BACKEND=postgres
export DB_URL=postgresql+psycopg://user:pass@host:5432/db

uv run python app.py

## Run with Gemini
export MODEL_PROVIDER=GEMINI
export GEMINI_API_KEY=...
uv run python app.py

## Hugging Face Space (CPU) using DuckDB + HF Datasets
- Push your heavy tables as dataset splits named: `taxon`, `assessment`, `habitat`, `image_asset`, `doc_chunk`, `occurrence`.
- In Space Secrets: set
  - `MODEL_PROVIDER=HF_LOCAL`
  - `HF_MODEL=microsoft/Phi-3-mini-4k-instruct` (or TinyLlama for small CPU)
  - `DB_BACKEND=duckdb`
  - `HF_DATASET_REPO=yourname/under-threat-species`
  - `BUILD_DUCK_FROM_HF=1`
- First startup will stream the dataset into `data/db.duckdb` and serve the app.

## Notes
- PostGIS features are not used on DuckDB; provide `longitude`/`latitude` columns in `occurrence` for bbox.
- WebResearcher uses Wikipedia + GBIF only (no paid keys). You can add Tavily later.