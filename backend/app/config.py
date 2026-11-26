from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CONTRACTS_DIR = REPO_ROOT / "contracts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_brain_model: str = "gemini-4-hydrogen"
    gemini_workhorse_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"

    default_execution_mode: str = "LIVE"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    embedding_dim: int = 768
    embedding_cache_ttl_seconds: int = 21600
    embedding_cache_max_entries: int = 1000
    max_active_runs: int = 20
    slayer_concurrency: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
