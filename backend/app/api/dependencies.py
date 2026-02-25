"""FastAPI dependency injection providers."""

from app.config.loader import config_loader
from app.mt5.client import mt5_client


async def get_mt5():
    """Dependency that provides the MT5 client."""
    return mt5_client


async def get_config():
    """Dependency that provides the config loader."""
    return config_loader
