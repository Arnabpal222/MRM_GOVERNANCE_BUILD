"""Application settings, read from environment variables (prefix MRM_) or AB_backend/.env."""
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent.parent  # .../MRM_Governance


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MRM_", env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "MRM Governance MIS"
    environment: str = "dev"

    database_url: str = "postgresql+psycopg://mrm:mrm_dev_password@localhost:5432/mrm"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "mrm_minio"
    minio_secret_key: str = "mrm_minio_password"
    minio_secure: bool = False
    minio_bucket: str = "mrm-documents"

    # "dev" enables the no-password login used by the header role switcher.
    # Production must use an OIDC provider (BRD §59); dev login is refused outside dev.
    auth_mode: str = "dev"
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    bootstrap_dir: Path = PROJECT_DIR / "B_Inputs" / "AA_bootstrap"
    sample_data_dir: Path = PROJECT_DIR / "B_Inputs" / "AB_sample_data"

    # Fixes "today" for demos and tests (YYYY-MM-DD). Unset in normal use.
    today_override: date | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
