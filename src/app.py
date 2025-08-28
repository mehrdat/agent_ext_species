from __future__ import annotations
import os
import gradio as gr
from src.graph.build_graph import build_graph, bootstrap, run_pipeline, execute_graph
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Optional: build DuckDB from HF Datasets if requested
if os.getenv("BUILD_DUCK_FROM_HF", "0") == "1":
    try:
        from src.data.hf_ingest import build_duckdb_from_hf
        path = build_duckdb_from_hf()
        print("Built DuckDB at", path)
    except Exception as e:
        print("DuckDB build skipped:", e)

app_graph = build_graph()
state0 = bootstrap()


def chat(user_msg: str):
    if not user_msg or not user_msg.strip():
        return {}, "Please enter a question about a species."
    s = dict(state0)
    s["user_input"] = user_msg.strip()
    try:
        out = execute_graph(app_graph, s)
    except Exception as e:
        # As a last resort attempt sequential path
        try:
            out = run_pipeline(user_msg)
        except Exception:
            return {}, f"Error: {type(e).__name__}: {e}"
    ui = out.get("ui_model") or {}
    md = out.get("markdown_report") or "No report."
    return ui, md

with gr.Blocks() as demo:
    gr.Markdown("# Under‑Threat Species Assistant")
    with gr.Row():
        inp = gr.Textbox(label="Ask about a species", placeholder="e.g., Show me status and images for Panthera leo")
    ui = gr.JSON(label="UI Model")
    md = gr.Markdown(label="Report")
    inp.submit(chat, inp, [ui, md])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)))