"""Centralised settings loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/portfolio_health"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    model_path: str = "models/health_scorer.ubj"
    feature_baseline_path: str = "models/feature_baseline.parquet"

    price_lookback_days: int = 365

    psi_threshold: float = 0.2
    score_drift_threshold: float = 10.0


settings = Settings()
