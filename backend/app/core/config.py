"""Core config - TRD Sec 21 env vars, PRD Sec 10."""
import os
from pydantic_settings import BaseSettings

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT}/data/osint.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT: int = 60
    GROQ_MAX_RETRIES: int = 3
    S3_ENDPOINT: str = "local"
    S3_BUCKET: str = "osint-evidence"
    EVIDENCE_DIR: str = f"{PROJECT_ROOT}/data/evidence"
    APP_SECRET_KEY: str = "change-me-dev-only"
    # Optional investigator-owned platform credentials (never logged/stored/sent to LLM).
    FB_USERNAME: str = ""
    FB_PASSWORD: str = ""
    IG_USERNAME: str = ""
    IG_PASSWORD: str = ""
    X_COOKIES_JSON: str = ""
    # Telegram: app credentials from my.telegram.org + investigator's own login.
    # TELEGRAM_2FA_PASSWORD / TELEGRAM_SESSION are as sensitive as a password.
    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: str = ""
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION: str = ""
    TELEGRAM_2FA_PASSWORD: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
# Ensure evidence dir exists (local S3-compatible layout)
os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
os.makedirs(f"{PROJECT_ROOT}/data", exist_ok=True)
