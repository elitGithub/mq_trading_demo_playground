"""Emergency kill switch - shuts down trading when critical thresholds are breached."""

import structlog

from app.config.loader import config_loader
from app.events.bus import event_bus
from app.events.events import Event, EventType
from app.mt5.client import mt5_client
from app.risk.manager import risk_manager

logger = structlog.get_logger()


class KillSwitch:
    """Monitors for critical conditions and emergency-closes all positions."""

    def _cfg(self, *keys, default=None):
        return config_loader.get_nested("risk", "risk", "kill_switch", *keys, default=default)

    async def check(self) -> None:
        """Check all kill switch conditions."""
        if not self._cfg("enabled", default=True):
            return

        account = await mt5_client.get_account_info()
        if account is None:
            return

        # Check drawdown
        max_dd = config_loader.get_nested("risk", "risk", "drawdown", "max_drawdown_pct", default=10.0)
        if account.balance > 0:
            drawdown_pct = ((account.balance - account.equity) / account.balance) * 100
            if drawdown_pct >= max_dd:
                await self.trigger(f"Max drawdown breached: {drawdown_pct:.1f}% >= {max_dd}%")
                return

        # Check consecutive losses
        max_consec = self._cfg("max_consecutive_losses", default=5)
        if risk_manager._consecutive_losses >= max_consec:
            await self.trigger(
                f"Max consecutive losses: {risk_manager._consecutive_losses} >= {max_consec}"
            )

    async def trigger(self, reason: str) -> None:
        """Trigger the kill switch: close all positions and halt trading."""
        logger.critical("kill_switch.triggered", reason=reason)

        # Halt the risk manager
        risk_manager.halt(reason)

        # Close all open positions
        positions = await mt5_client.get_positions()
        for pos in positions:
            result = await mt5_client.close_position(pos.ticket)
            if result.success:
                logger.info("kill_switch.closed_position", ticket=pos.ticket)
            else:
                logger.error("kill_switch.close_failed", ticket=pos.ticket, error=result.comment)

        # Publish event
        await event_bus.publish(Event(
            type=EventType.KILL_SWITCH_TRIGGERED,
            data={"reason": reason, "positions_closed": len(positions)},
            source="kill_switch",
        ))


# Global instance
kill_switch = KillSwitch()
