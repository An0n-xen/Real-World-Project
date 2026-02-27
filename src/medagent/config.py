import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application-wide settings."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── DeepInfra ──────────────────────────────────────────────
    deepinfra_api_key: str = ""
    deepinfra_base_url: str = "https://api.deepinfra.com/v1/openai"

    # ── SerpAPI ────────────────────────────────────────────────
    serpapi_api_key: str = ""

    # ── Model names ────────────────────────────────────────────
    primary_vlm_model: str = "Qwen/Qwen2.5-VL-32B-Instruct"
    # primary_vlm_model: str = "Qwen/Qwen3-VL-235B-A22B-Instruct"
    text_llm_model: str = "Qwen/Qwen2.5-72B-Instruct"

    # ── RAG ────────────────────────────────────────────────────
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5
    embedding_model: str = "BAAI/bge-large-en-v1.5"

    # ── Paths ──────────────────────────────────────────────────
    diseases_dir: str = str(_PROJECT_ROOT / "diseases")
    output_dir: str = str(_PROJECT_ROOT / "output")

    # ── Logging ────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── LangSmith ──────────────────────────────────────────────
    langsmith_api_key: str = ""
    langsmith_project: str = "medagent-pro"
    # Set to "true" to enable LangSmith tracing
    langchain_tracing_v2: str = "true"
    langchain_endpoint: str = "https://api.smith.langchain.com"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


def configure_langsmith() -> bool:
    """Configure LangSmith tracing from settings.

    Sets the environment variables that LangChain / LangGraph read
    automatically (``LANGCHAIN_TRACING_V2``, ``LANGCHAIN_API_KEY``,
    ``LANGCHAIN_PROJECT``, ``LANGCHAIN_ENDPOINT``).

    Must be called **before** any LangChain component is initialised so
    the tracer is registered from the start.

    Returns:
        ``True`` if tracing is enabled, ``False`` otherwise.
    """
    from medagent.logger import get_logger
    logger = get_logger("medagent.langsmith")

    s = get_settings()

    # LangChain reads these specific env var names
    os.environ["LANGCHAIN_TRACING_V2"] = s.langchain_tracing_v2
    os.environ["LANGCHAIN_ENDPOINT"] = s.langchain_endpoint
    os.environ["LANGCHAIN_PROJECT"] = s.langsmith_project

    if s.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = s.langsmith_api_key

    tracing_on = s.langchain_tracing_v2.lower() == "true"

    if tracing_on:
        if not s.langsmith_api_key:
            logger.warning(
                "LangSmith tracing enabled but LANGSMITH_API_KEY is not set — "
                "traces will not be uploaded."
            )
        else:
            logger.info(
                "LangSmith tracing ENABLED  project=%s  endpoint=%s",
                s.langsmith_project,
                s.langchain_endpoint,
            )
    else:
        logger.info("LangSmith tracing DISABLED (set LANGCHAIN_TRACING_V2=true to enable)")

    return tracing_on
