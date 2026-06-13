"""Application configuration via environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All settings are loaded from environment variables (or .env file).
    GEOCODING_API_KEY lives in Google Secret Manager on Cloud Run,
    mounted as env var. Locally in .env (gitignored).
    """

    STORAGE_BUCKET: str
    GEOCODING_API_KEY: str
    MAX_PHOTO_BYTES: int = 10 * 1024 * 1024  # 10 MB
    # TTL for the in-process spots snapshot that backs the nearby + search scans.
    SPOT_CACHE_TTL_SECONDS: int = 45
    FIREBASE_CREDENTIALS_PATH: str | None = None
    ENV: Literal["dev", "prod", "test"] = "dev"
    CORS_ORIGINS: list[str] = ["*"]
    # Legal documents — hosted on Firebase Hosting. Env-overridable so a future
    # custom domain needs no code change. Surfaced to the client via GET /legal.
    PRIVACY_POLICY_URL: str = "https://scout-497021.web.app/privacy"
    TERMS_OF_SERVICE_URL: str = "https://scout-497021.web.app/terms"
    # ISO date the legal documents were last revised (shown by GET /legal).
    LEGAL_UPDATED_AT: str = "2026-06-12"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
