"""Signal generation - evaluates price action near detected levels."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.config.loader import config_loader
from app.mt5.models import Bar
from app.strategy.price_levels import PriceLevel

logger = structlog.get_logger()


@dataclass
class Signal:
    """A trading signal generated when price reacts to a level."""
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    level: PriceLevel
    confidence: float = 0.0
    strategy_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SignalGenerator:
    """Generates trading signals based on price-level reactions. Config-driven."""

    def evaluate(
        self,
        symbol: str,
        bars: list[Bar],
        nearby_levels: list[PriceLevel],
        current_atr: float,
        strategy_cfg: dict,
        strategy_id: str = "",
    ) -> Signal | None:
        """
        Evaluate whether recent price action at a nearby level generates a signal.

        All thresholds come from the resolved strategy_cfg dict.
        """
        if not bars or not nearby_levels or current_atr <= 0:
            return None

        entry_cfg = strategy_cfg.get("entry", {})
        exit_cfg = strategy_cfg.get("exit", {})
        confirmation_candles = entry_cfg.get("confirmation_candles", 2)
        min_rejection_pips = entry_cfg.get("min_rejection_pips", 10)
        tp_atr = exit_cfg.get("take_profit_atr_multiplier", 2.0)
        sl_atr = exit_cfg.get("stop_loss_atr_multiplier", 1.0)

        # Get symbol pip size from config
        symbols_cfg = config_loader.get("symbols")
        instruments = symbols_cfg.get("symbols", {}).get("instruments", {})
        defaults = symbols_cfg.get("symbols", {}).get("defaults", {})
        pip_size = instruments.get(symbol, {}).get("pip_size", defaults.get("pip_size", 0.0001))

        if len(bars) < confirmation_candles + 1:
            return None

        recent_bars = bars[-(confirmation_candles + 1):]
        current_bar = recent_bars[-1]

        for level in nearby_levels:
            if not level.is_active:
                continue

            signal = self._check_level_reaction(
                symbol, level, recent_bars, current_bar,
                current_atr, pip_size, min_rejection_pips,
                tp_atr, sl_atr, strategy_id,
            )
            if signal:
                return signal

        return None

    def _check_level_reaction(
        self,
        symbol: str,
        level: PriceLevel,
        recent_bars: list[Bar],
        current_bar: Bar,
        atr: float,
        pip_size: float,
        min_rejection_pips: float,
        tp_atr: float,
        sl_atr: float,
        strategy_id: str = "",
    ) -> Signal | None:
        """Check if price is reacting (rejecting) at a level."""
        price = current_bar.close

        # Support bounce (buy signal)
        if level.level_type == "support" and level.zone_lower <= current_bar.low <= level.zone_upper:
            # Check for rejection wick
            wick = current_bar.close - current_bar.low
            if wick / pip_size >= min_rejection_pips:
                # Check confirmation: price closing above level
                if price > level.price:
                    sl = level.zone_lower - (atr * sl_atr)
                    tp = price + (atr * tp_atr)
                    return Signal(
                        symbol=symbol,
                        side="BUY",
                        entry_price=price,
                        stop_loss=sl,
                        take_profit=tp,
                        level=level,
                        confidence=level.strength,
                        strategy_id=strategy_id,
                    )

        # Resistance rejection (sell signal)
        if level.level_type == "resistance" and level.zone_lower <= current_bar.high <= level.zone_upper:
            wick = current_bar.high - current_bar.close
            if wick / pip_size >= min_rejection_pips:
                if price < level.price:
                    sl = level.zone_upper + (atr * sl_atr)
                    tp = price - (atr * tp_atr)
                    return Signal(
                        symbol=symbol,
                        side="SELL",
                        entry_price=price,
                        stop_loss=sl,
                        take_profit=tp,
                        level=level,
                        confidence=level.strength,
                        strategy_id=strategy_id,
                    )

        return None
