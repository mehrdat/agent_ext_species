from __future__ import annotations
import os
from typing import Any

# Providers: OLLAMA (local), GEMINI (Google), HF_LOCAL (transformers on CPU/GPU)
PROVIDER = os.getenv("MODEL_PROVIDER", "OLLAMA").upper()

# ---- OLLAMA (local) ---------------------------------------------------------
# pip install langchain-community

def _ollama() -> Any:
    from langchain_community.chat_models import ChatOllama
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    return ChatOllama(base_url=base_url, model=model, temperature=0.2)

# ---- GEMINI (Google Generative AI) -----------------------------------------
# pip install langchain-google-genai google-generativeai

def _gemini() -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY/GOOGLE_API_KEY not set")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return ChatGoogleGenerativeAI(model=model, api_key=api_key, temperature=0.2)

# ---- HF_LOCAL (transformers) -----------------------------------------------
# pip install transformers accelerate torch --extra-index-url https://download.pytorch.org/whl/cpu

def _hf_local() -> Any:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    from langchain_community.llms import HuggingFacePipeline
    hf_model = os.getenv("HF_MODEL", "Qwen2.5-3B-Instruct")
    device = 0 if os.getenv("USE_GPU", "0") == "1" else -1
    tokenizer = AutoTokenizer.from_pretrained(hf_model)
    model = AutoModelForCausalLM.from_pretrained(hf_model, device_map="auto" if device == 0 else None)
    gen = pipeline("text-generation", model=model, tokenizer=tokenizer, device=device, max_new_tokens=512)
    return HuggingFacePipeline(pipeline=gen)

# Public factory used by your agents

def get_llm() -> Any:
    if PROVIDER == "OLLAMA":
        return _ollama()
    if PROVIDER == "GEMINI":
        return _gemini()
    if PROVIDER == "HF_LOCAL":
        return _hf_local()
    raise ValueError(f"Unknown MODEL_PROVIDER: {PROVIDER}")