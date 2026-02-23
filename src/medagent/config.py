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
    # primary_vlm_model: str = "Qwen/Qwen2.5-VL-32B-Instruct"
    primary_vlm_model: str = "Qwen/Qwen3-VL-235B-A22B-Instruct"
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
