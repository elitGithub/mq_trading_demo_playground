"""Trading service - trade execution and logging."""

import structlog

from app.mt5.client import mt5_client

logger = structlog.get_logger()


class TradingService:
    """Business logic for trade execution."""

    async def get_open_trades_summary(self) -> dict:
        """Get summary of all open trades."""
        positions = await mt5_client.get_positions()
        total_profit = sum(p.profit for p in positions)
        total_volume = sum(p.volume for p in positions)
        return {
            "count": len(positions),
            "total_profit": total_profit,
            "total_volume": total_volume,
        }


trading_service = TradingService()
