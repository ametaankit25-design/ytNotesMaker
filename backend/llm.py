import os
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _clean_key(key: str | None) -> str | None:
    if not key:
        return None
    cleaned = key.strip().strip('"').strip("'")
    return cleaned if cleaned else None


def llm_model(model_name="llama3.2", temperature=0):
    """
    Returns an LLM model instance based on environment configuration.

    Priority:
      1. Groq Cloud: GROQ_API_KEY
      2. Gemini Cloud: GEMINI_API_KEY / GOOGLE_API_KEY
      3. OpenAI: OPENAI_API_KEY
      4. Local Ollama: OLLAMA_BASE_URL
    """
    groq_api_key   = _clean_key(os.getenv("GROQ_API_KEY"))
    gemini_api_key = _clean_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    openai_api_key = _clean_key(os.getenv("OPENAI_API_KEY"))

    if groq_api_key:
        print("[LLM Engine] Using Groq Cloud API (llama-3.3-70b-versatile)")
        return ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=temperature,
            api_key=groq_api_key,
        )
    elif gemini_api_key:
        print("[LLM Engine] Using Gemini Cloud API")
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            temperature=temperature,
            google_api_key=gemini_api_key,
        )
    elif openai_api_key:
        print("[LLM Engine] Using OpenAI API")
        return ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=temperature,
            api_key=openai_api_key,
        )
    else:
        print(f"[LLM Engine] Using Local Ollama ({model_name}) at {_OLLAMA_BASE_URL}")
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=_OLLAMA_BASE_URL,
        )


def embeddings_model(model_name="nomic-embed-text"):
    openai_api_key = _clean_key(os.getenv("OPENAI_API_KEY"))
    if openai_api_key:
        return OpenAIEmbeddings(api_key=openai_api_key)
    else:
        return OllamaEmbeddings(
            model=model_name,
            base_url=_OLLAMA_BASE_URL,
        )