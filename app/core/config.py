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
    FIREBASE_CREDENTIALS_PATH: str | None = None
    ENV: Literal["dev", "prod", "test"] = "dev"
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
