from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CONTRACTS_DIR = REPO_ROOT / "contracts"
EXPORTS_DIR = REPO_ROOT / "exports"
CRM_DNC_FILE = DATA_DIR / "crm_dnc.json"
GMAIL_OAUTH_TOKEN_FILE = DATA_DIR / ".gmail_oauth_token.json"
HARVEY_ROOT = REPO_ROOT / "harvey"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Accepts a single key OR a comma-separated pool: key1,key2,key3
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

    # Optional Harvey Tier B/C integrations (zero cost; leave blank for safe sandbox)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_from_name: str = "LeadSlayer"
    smtp_from_email: str = ""
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    linkedin_email: str = ""
    linkedin_password: str = ""
    do_not_contact_domains: str = ""
    sender_postal_address: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gemini_api_key_pool(self) -> list[str]:
        """Return all API keys; supports comma-separated pool: key1,key2,key3."""
        return [k.strip() for k in self.gemini_api_key.split(",") if k.strip()]


settings = Settings()
