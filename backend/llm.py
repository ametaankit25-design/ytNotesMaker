import os
from langchain_ollama import ChatOllama, OllamaEmbeddings

# In Docker, Ollama runs as a separate container.
# Set OLLAMA_BASE_URL=http://ollama:11434 in docker-compose.
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def llm_model(model_name="llama3.2", temperature=0):
    """
    Returns a ChatOllama instance.

    Reads OLLAMA_BASE_URL from environment (default: http://localhost:11434).
    In Docker Compose, set OLLAMA_BASE_URL=http://ollama:11434.
    """
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=_OLLAMA_BASE_URL,
    )


def embeddings_model(model_name="nomic-embed-text"):
    """
    Returns an OllamaEmbeddings instance.

    Reads OLLAMA_BASE_URL from environment (default: http://localhost:11434).
    """
    return OllamaEmbeddings(
        model=model_name,
        base_url=_OLLAMA_BASE_URL,
    )