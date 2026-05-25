"""Application configuration using pydantic-settings.

All values are read from environment variables (or a .env file).
Secrets have no defaults — the application will fail to start if they are missing.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra fields in .env are silently ignored
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    # Full async-compatible PostgreSQL connection string.
    # Example: postgresql+asyncpg://fluency:password@db:5432/fluency
    database_url: str

    # Postgres password (used by the db service directly, not by the API)
    postgres_password: str = ""

    # ------------------------------------------------------------------ #
    # Authentication                                                       #
    # ------------------------------------------------------------------ #
    # Long random secret used to sign JWTs — no default; must be supplied.
    jwt_secret: str

    # ------------------------------------------------------------------ #
    # Stripe                                                               #
    # ------------------------------------------------------------------ #
    stripe_secret_key: str
    stripe_webhook_secret: str

    # ------------------------------------------------------------------ #
    # Resend (transactional email)                                         #
    # ------------------------------------------------------------------ #
    resend_api_key: str

    # ------------------------------------------------------------------ #
    # Daily.co (video lessons)                                             #
    # ------------------------------------------------------------------ #
    daily_api_key: str

    # ------------------------------------------------------------------ #
    # Application                                                          #
    # ------------------------------------------------------------------ #
    # Public URL of the frontend, used for CORS and email links.
    frontend_url: str

    # Deployment environment: development | staging | production
    environment: str = "development"


# Module-level singleton — import this everywhere settings are needed.
settings = Settings()
