"""Strategy config API routes - CRUD for YAML config files."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.loader import config_loader

router = APIRouter(prefix="/strategy", tags=["strategy"])

VALID_CONFIGS = {"strategy", "price_levels", "risk", "symbols", "notifications", "trade_plans"}


class ConfigUpdate(BaseModel):
    data: dict


@router.get("/config/{name}")
async def get_config(name: str):
    """Get a config file contents."""
    if name not in VALID_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown config: {name}")
    return {"name": name, "data": config_loader.get(name)}


@router.put("/config/{name}")
async def update_config(name: str, body: ConfigUpdate):
    """Update a config file. Saves history and hot-reloads."""
    if name not in VALID_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown config: {name}")
    config_loader.update(name, body.data, changed_by="api")
    return {"status": "ok", "name": name}


@router.get("/config/{name}/history")
async def get_config_history(name: str):
    """List config history snapshots."""
    if name not in VALID_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown config: {name}")
    return {"name": name, "history": config_loader.get_history(name)}


@router.get("/status")
async def get_strategy_status():
    """Get strategy engine status with per-strategy info and symbol assignments."""
    enabled_strategies = config_loader.get_enabled_strategies()
    all_strategies = config_loader.get("strategy").get("strategies", {})

    # Build symbol -> strategy_id mapping
    symbol_strategies = {}
    for symbol in config_loader.get_enabled_symbols():
        result = config_loader.get_strategy_for_symbol(symbol)
        symbol_strategies[symbol] = result[0] if result else None

    return {
        "enabled": config_loader.is_strategy_enabled(),
        "symbols": config_loader.get_enabled_symbols(),
        "strategies": {
            sid: {"name": cfg.get("name", sid), "enabled": cfg.get("enabled", False)}
            for sid, cfg in all_strategies.items()
        },
        "enabled_strategies": list(enabled_strategies.keys()),
        "symbol_strategies": symbol_strategies,
    }
