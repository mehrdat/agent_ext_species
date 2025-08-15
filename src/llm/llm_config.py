

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage


load_dotenv()



def llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in environment")
    llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0.0, max_tokens=900)
    print("[LLM] Gemini initialized:", model_name)

    return llm