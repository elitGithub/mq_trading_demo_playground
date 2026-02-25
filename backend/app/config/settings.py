"""Application settings from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # MT5 Connection
    mt5_host: str = "mt5"
    mt5_port: int = 8001
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://trader:changeme_db_password@timescaledb:5432/trading"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # App
    log_level: str = "INFO"
    config_dir: str = "/app/config"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
