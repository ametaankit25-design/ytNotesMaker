import os

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _clean_key(key: str | None) -> str | None:
    if not key:
        return None
    cleaned = key.strip().strip('"').strip("'")
    return cleaned if cleaned else None


def llm_model(model_name="llama3.2", temperature=0):
    """
    Returns an LLM model instance based on environment configuration.
    Uses dynamic imports so missing optional packages never crash backend startup.
    """
    groq_api_key   = _clean_key(os.getenv("GROQ_API_KEY"))
    gemini_api_key = _clean_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    openai_api_key = _clean_key(os.getenv("OPENAI_API_KEY"))

    if groq_api_key:
        print("[LLM Engine] Using Groq Cloud API (llama-3.3-70b-versatile)")
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name="llama-3.3-70b-versatile",
                temperature=temperature,
                api_key=groq_api_key,
            )
        except ImportError as e:
            raise RuntimeError(f"langchain-groq module missing: {e}")

    if gemini_api_key:
        print("[LLM Engine] Using Gemini Cloud API")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-lite",
                temperature=temperature,
                google_api_key=gemini_api_key,
            )
        except ImportError as e:
            raise RuntimeError(f"langchain-google-genai module missing: {e}")

    if openai_api_key:
        print("[LLM Engine] Using OpenAI API")
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model_name="gpt-4o-mini",
                temperature=temperature,
                api_key=openai_api_key,
            )
        except ImportError as e:
            raise RuntimeError(f"langchain-openai module missing: {e}")

    # Fallback to Ollama
    print(f"[LLM Engine] Using Local Ollama ({model_name}) at {_OLLAMA_BASE_URL}")
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=_OLLAMA_BASE_URL,
        )
    except ImportError:
        raise RuntimeError("No cloud LLM API key provided (GROQ_API_KEY), and langchain-ollama is not installed.")


def embeddings_model(model_name="nomic-embed-text"):
    openai_api_key = _clean_key(os.getenv("OPENAI_API_KEY"))
    if openai_api_key:
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(api_key=openai_api_key)
        except ImportError:
            pass

    try:
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=model_name,
            base_url=_OLLAMA_BASE_URL,
        )
    except ImportError:
        return None