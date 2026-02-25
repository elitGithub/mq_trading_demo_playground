"""Account service - account monitoring and equity tracking."""

import structlog

from app.mt5.client import mt5_client

logger = structlog.get_logger()


class AccountService:
    """Business logic for account operations."""

    async def get_account_summary(self) -> dict | None:
        """Get account summary with derived metrics."""
        info = await mt5_client.get_account_info()
        if info is None:
            return None

        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
            "margin_level": info.margin_level,
            "profit": info.profit,
            "drawdown_pct": ((info.balance - info.equity) / info.balance * 100)
            if info.balance > 0 else 0,
        }


account_service = AccountService()
