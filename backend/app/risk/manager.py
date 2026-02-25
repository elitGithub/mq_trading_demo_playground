"""Risk manager - pre-trade checks and position sizing. Config-driven."""

from datetime import datetime, timezone

import structlog

from app.config.loader import config_loader
from app.mt5.client import mt5_client
from app.strategy.signals import Signal

logger = structlog.get_logger()


class RiskManager:
    """Validates trades against risk limits defined in risk.yaml."""

    def __init__(self):
        self._daily_loss: float = 0.0
        self._daily_trades: int = 0
        self._consecutive_losses: int = 0
        self._last_reset_date: str = ""
        self._halted: bool = False

    def _cfg(self, *keys, default=None):
        return config_loader.get_nested("risk", "risk", *keys, default=default)

    async def check_trade(self, signal: Signal) -> tuple[bool, str]:
        """Run all risk checks before allowing a trade. Returns (allowed, reason)."""
        if self._halted:
            return False, "Trading halted by kill switch"

        self._check_daily_reset()

        checks = [
            self._check_daily_loss,
            self._check_daily_trades,
            self._check_max_positions,
            self._check_position_per_symbol,
            self._check_spread,
            self._check_trading_hours,
        ]

        for check in checks:
            ok, reason = await check(signal)
            if not ok:
                return False, reason

        return True, "OK"

    async def calculate_position_size(
        self, symbol: str, entry_price: float, stop_loss: float
    ) -> float:
        """Calculate position size based on risk config."""
        method = self._cfg("sizing", "method", default="fixed_percentage")

        if method == "fixed_lot":
            return self._cfg("sizing", "fixed_lot_size", default=0.01)

        # Fixed percentage method
        account = await mt5_client.get_account_info()
        if account is None:
            return self._cfg("sizing", "fixed_lot_size", default=0.01)

        max_risk_pct = self._cfg("per_trade", "max_risk_pct", default=1.0)
        risk_amount = account.balance * (max_risk_pct / 100)

        # Get pip size
        symbols_cfg = config_loader.get("symbols")
        instruments = symbols_cfg.get("symbols", {}).get("instruments", {})
        defaults = symbols_cfg.get("symbols", {}).get("defaults", {})
        pip_size = instruments.get(symbol, {}).get("pip_size", defaults.get("pip_size", 0.0001))

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return self._cfg("sizing", "fixed_lot_size", default=0.01)

        sl_pips = sl_distance / pip_size
        if sl_pips <= 0:
            return self._cfg("sizing", "fixed_lot_size", default=0.01)

        # Approximate pip value (simplified - assumes USD account)
        pip_value_per_lot = pip_size * 100000  # Standard lot

        volume = risk_amount / (sl_pips * pip_value_per_lot)

        # Clamp to limits
        min_vol = instruments.get(symbol, {}).get("min_volume", defaults.get("min_volume", 0.01))
        max_vol = self._cfg("per_trade", "max_volume", default=10.0)
        vol_step = instruments.get(symbol, {}).get("volume_step", defaults.get("volume_step", 0.01))

        volume = max(min_vol, min(volume, max_vol))
        volume = round(volume / vol_step) * vol_step
        volume = round(volume, 2)

        return volume

    def record_trade_result(self, pnl: float) -> None:
        """Record a trade result for daily tracking."""
        self._daily_trades += 1
        if pnl < 0:
            self._daily_loss += abs(pnl)
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def halt(self, reason: str) -> None:
        """Halt all trading."""
        self._halted = True
        logger.critical("risk.halted", reason=reason)

    def resume(self) -> None:
        """Resume trading after halt."""
        self._halted = False
        logger.info("risk.resumed")

    def _check_daily_reset(self) -> None:
        """Reset daily counters at the configured hour."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._daily_loss = 0.0
            self._daily_trades = 0
            self._last_reset_date = today

    async def _check_daily_loss(self, signal: Signal) -> tuple[bool, str]:
        max_loss = self._cfg("daily", "max_daily_loss_pct", default=3.0)
        account = await mt5_client.get_account_info()
        if account and account.balance > 0:
            loss_pct = (self._daily_loss / account.balance) * 100
            if loss_pct >= max_loss:
                return False, f"Daily loss limit reached ({loss_pct:.1f}% >= {max_loss}%)"
        return True, ""

    async def _check_daily_trades(self, signal: Signal) -> tuple[bool, str]:
        max_trades = self._cfg("daily", "max_daily_trades", default=20)
        if self._daily_trades >= max_trades:
            return False, f"Daily trade limit reached ({self._daily_trades} >= {max_trades})"
        return True, ""

    async def _check_max_positions(self, signal: Signal) -> tuple[bool, str]:
        max_pos = self._cfg("portfolio", "max_open_positions", default=5)
        positions = await mt5_client.get_positions()
        if len(positions) >= max_pos:
            return False, f"Max positions reached ({len(positions)} >= {max_pos})"
        return True, ""

    async def _check_position_per_symbol(self, signal: Signal) -> tuple[bool, str]:
        max_per_symbol = self._cfg("portfolio", "max_positions_per_symbol", default=2)
        positions = await mt5_client.get_positions(signal.symbol)
        if len(positions) >= max_per_symbol:
            return False, f"Max positions for {signal.symbol} ({len(positions)} >= {max_per_symbol})"
        return True, ""

    async def _check_spread(self, signal: Signal) -> tuple[bool, str]:
        symbols_cfg = config_loader.get("symbols")
        instruments = symbols_cfg.get("symbols", {}).get("instruments", {})
        defaults = symbols_cfg.get("symbols", {}).get("defaults", {})
        spread_limit = instruments.get(signal.symbol, {}).get(
            "spread_limit_pips", defaults.get("spread_limit_pips", 5)
        )
        pip_size = instruments.get(signal.symbol, {}).get(
            "pip_size", defaults.get("pip_size", 0.0001)
        )

        tick = await mt5_client.get_tick(signal.symbol)
        if tick:
            spread_pips = (tick.ask - tick.bid) / pip_size
            if spread_pips > spread_limit:
                return False, f"Spread too wide ({spread_pips:.1f} > {spread_limit} pips)"
        return True, ""

    async def _check_trading_hours(self, signal: Signal) -> tuple[bool, str]:
        if not self._cfg("trading_hours", "enabled", default=False):
            return True, ""

        now = datetime.now(timezone.utc)
        day = now.weekday()  # 0=Monday

        excluded = self._cfg("trading_hours", "excluded_days", default=[5, 6])
        if day in excluded:
            return False, f"Trading not allowed on day {day}"

        sessions = self._cfg("trading_hours", "sessions", default=[])
        current_time = now.strftime("%H:%M")

        for session in sessions:
            if session.get("start", "00:00") <= current_time <= session.get("end", "23:59"):
                return True, ""

        if sessions:
            return False, "Outside trading hours"
        return True, ""


# Global instance
risk_manager = RiskManager()
