import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _try_parse_db_url_from_db_connection_txt(text: str) -> Optional[str]:
    """
    Parse db URL from the DB container's db_connection.txt content.

    The DB container writes a line like:
        psql postgresql://user:pass@localhost:5000/myapp
    """
    text = (text or "").strip()
    if not text:
        return None
    # Accept both "psql postgresql://..." and bare "postgresql://..."
    if "postgresql://" in text:
        idx = text.find("postgresql://")
        return text[idx:].strip()
    if text.startswith("postgres://"):
        return text.strip()
    return None


def _resolve_repo_root() -> Path:
    """
    Best-effort repo root discovery.
    This file lives at: fastapi_backend/src/core/config.py
    Repo root is typically: .../unified-task-planner-.../ (two parents above fastapi_backend)
    """
    return Path(__file__).resolve().parents[3]


# PUBLIC_INTERFACE
def get_database_url() -> str:
    """
    Returns the database connection URL.

    Resolution order:
    1) DATABASE_URL env var (recommended in production)
    2) postgresql_database/db_connection.txt (generated at runtime by DB container)
    3) fallback to a safe default useful for local dev

    If db_connection.txt doesn't exist yet, we *gracefully* fall back without crashing.
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    repo_root = _resolve_repo_root()
    db_conn_path = repo_root / "postgresql_database" / "db_connection.txt"
    try:
        if db_conn_path.exists():
            raw = db_conn_path.read_text(encoding="utf-8")
            parsed = _try_parse_db_url_from_db_connection_txt(raw)
            if parsed:
                return parsed
    except Exception:
        # Gracefully ignore; DB may be starting or file may be mid-write.
        pass

    # Fallback matches DB container defaults (see postgresql_database/startup.sh)
    return "postgresql+asyncpg://appuser:dbuser123@localhost:5000/myapp"


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the FastAPI backend."""
    app_name: str = os.getenv("APP_NAME", "Unified Task Planner API")
    app_version: str = os.getenv("APP_VERSION", "0.2.0")

    # NOTE: request orchestrator to set this in .env for production.
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-insecure-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    access_token_expires_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", "30"))
    refresh_token_expires_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "14"))

    cors_allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "*")

    database_url: str = get_database_url()


settings = Settings()
