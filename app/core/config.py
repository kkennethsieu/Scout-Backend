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
    # iOS app version gating — surfaced via GET /config. Client compares its build
    # against these and shows a blocking "update required" (< min) or dismissible
    # "update available" (< latest) prompt. Env-overridable so versions bump without
    # a code change. Placeholder defaults (min == latest) gate no build until set.
    IOS_MIN_VERSION: str = "1.0"
    IOS_LATEST_VERSION: str = "1.0.1"
    IOS_UPDATE_URL: str = "https://apps.apple.com/us/app/scout-photo-locations/id6781030287"
    # Firebase App Check. When False, a missing/invalid X-Firebase-AppCheck header
    # is logged but allowed through (so the API keeps working before the iOS app
    # ships the App Check SDK). Flip to True via env once the client sends tokens.
    APP_CHECK_ENFORCED: bool = False

    # --- AI review summaries (Google Gemini) ---
    # GEMINI_API_KEY lives in Secret Manager on Cloud Run (mounted as env var),
    # locally in .env. Empty default so the app still boots without it; generation
    # is a no-op until AI_SUMMARIES_ENABLED is on AND a key is present.
    GEMINI_API_KEY: str = ""
    # Cheap flash-tier default; env-overridable so the exact model id can be
    # swapped without a code change.
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    # Master switch for runtime summary generation. Kill-switch via env.
    AI_SUMMARIES_ENABLED: bool = True
    # Don't summarize a spot until it has at least this many reviews.
    AI_SUMMARY_MIN_REVIEWS: int = 3
    # Regenerate once review_count has grown by this much since the last summary.
    AI_SUMMARY_REFRESH_EVERY: int = 5

    # --- Nearby-spots fallback ---
    # When GET /spots finds nothing near the caller (first page), fall back to the
    # spots around a predefined flagship location so the map/feed is never blank.
    # The result is flagged is_fallback=true so the client can label it. Kill-switch
    # + location + radius are env-overridable (no app release to retune the flagship).
    NEARBY_FALLBACK_ENABLED: bool = True
    FALLBACK_LAT: float = 34.0522  # Los Angeles
    FALLBACK_LNG: float = -118.2437
    FALLBACK_RADIUS_KM: float = 100.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
