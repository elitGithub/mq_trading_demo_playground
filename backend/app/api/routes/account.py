"""Account API routes."""

from fastapi import APIRouter

from app.mt5.client import mt5_client

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/info")
async def get_account_info():
    """Get MT5 account information."""
    info = await mt5_client.get_account_info()
    if info is None:
        return {"account": None, "connected": mt5_client.connected}
    return {
        "account": {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
            "margin_level": info.margin_level,
            "profit": info.profit,
            "currency": info.currency,
            "leverage": info.leverage,
            "server": info.server,
            "name": info.name,
            "company": info.company,
        },
        "connected": mt5_client.connected,
    }
