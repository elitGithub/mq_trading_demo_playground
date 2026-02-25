"""Strategy engine - the central orchestrator. Fully config-driven."""

import asyncio

import structlog

from app.config.loader import config_loader
from app.events.bus import event_bus
from app.events.events import Event, EventType
from app.mt5.client import mt5_client
from app.mt5.models import Tick
from app.services.market_data_service import market_data_service
from app.strategy.price_levels import PriceLevelDetector
from app.strategy.rule_engine import rule_engine

logger = structlog.get_logger()


class StrategyEngine:
    """Main strategy loop. Reads all behavior from config files."""

    def __init__(self):
        self.level_detector = PriceLevelDetector()
        self._running = False
        self._task: asyncio.Task | None = None
        self._tick_cursors: dict[str, int] = {}  # symbol -> last processed time_msc

    async def start(self) -> None:
        """Start the strategy engine loop."""
        await rule_engine.load_plans()
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("strategy.engine.started")

    async def stop(self) -> None:
        """Stop the strategy engine."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await rule_engine.save_all_state()
        logger.info("strategy.engine.stopped")

    async def _run(self) -> None:
        """Main strategy loop - polls MT5 and evaluates rules."""
        while self._running:
            try:
                poll_ms = config_loader.get_nested(
                    "strategy", "poll_interval_ms", default=500
                )

                if not config_loader.is_strategy_enabled():
                    await asyncio.sleep(poll_ms / 1000)
                    continue

                if not mt5_client.connected:
                    logger.warning("strategy.mt5_disconnected")
                    await asyncio.sleep(5)
                    continue

                symbols = set(config_loader.get_enabled_symbols())
                # Include symbols from active trade plans
                for plan in rule_engine.plans.values():
                    if plan.enabled:
                        symbols.add(plan.symbol)
                for symbol in symbols:
                    await self._process_symbol(symbol)

                await asyncio.sleep(poll_ms / 1000)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("strategy.engine.error")
                await asyncio.sleep(5)

    async def _process_symbol(self, symbol: str) -> None:
        """Process a single symbol: detect levels for UI, evaluate trade plan rules."""
        try:
            # Resolve strategy for this symbol (used for level detection config)
            result = config_loader.get_strategy_for_symbol(symbol)
            if result is not None:
                strategy_id, strategy_cfg = result

                # Get analysis timeframes from the resolved strategy
                timeframes_cfg = strategy_cfg.get("timeframes", {})
                analysis_tfs = timeframes_cfg.get("analysis", ["H1"])

                # Detect levels on analysis timeframes (kept for UI overlay)
                for tf in analysis_tfs:
                    bars = await mt5_client.get_bars(symbol, tf, 300)
                    if bars:
                        levels = self.level_detector.detect_levels(symbol, bars, tf)
                        for level in levels:
                            await event_bus.publish(Event(
                                type=EventType.LEVEL_DETECTED,
                                data={
                                    "symbol": symbol,
                                    "price": level.price,
                                    "type": level.level_type,
                                    "strategy_id": strategy_id,
                                },
                                source="strategy_engine",
                            ))

            # Batch tick retrieval and rule evaluation
            last_msc = self._tick_cursors.get(symbol, 0)

            if last_msc == 0:
                # Bootstrap: seed cursor from latest tick, don't replay history
                tick = await mt5_client.get_tick(symbol)
                if tick:
                    self._tick_cursors[symbol] = (
                        tick.time_msc if tick.time_msc > 0
                        else int(tick.time.timestamp() * 1000)
                    )
                    rule_engine.begin_cycle()
                    await rule_engine.evaluate(symbol, tick)
                    await self._publish_tick(tick)
                return

            batch_size = config_loader.get_nested(
                "strategy", "tick_batch_size", default=500
            )
            ticks = await mt5_client.get_ticks_since(symbol, last_msc, batch_size)

            # Filter out the boundary tick (API is inclusive on from_msc)
            ticks = [t for t in ticks if t.time_msc > last_msc]

            if not ticks:
                return

            rule_engine.begin_cycle()
            for tick in ticks:
                await rule_engine.evaluate(symbol, tick)

            # Advance cursor and publish the latest tick
            self._tick_cursors[symbol] = ticks[-1].time_msc
            await self._publish_tick(ticks[-1])

            if len(ticks) > 1:
                logger.debug(
                    "strategy.tick_batch",
                    symbol=symbol,
                    count=len(ticks),
                )

        except Exception:
            logger.exception("strategy.process_symbol_error", symbol=symbol)

    async def _publish_tick(self, tick: Tick) -> None:
        """Cache tick in Redis and publish TICK event for WS broadcast."""
        await market_data_service.cache_tick(tick)
        await event_bus.publish(Event(
            type=EventType.TICK,
            data={
                "symbol": tick.symbol,
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "time": tick.time.isoformat(),
                "time_msc": tick.time_msc,
            },
            source="strategy_engine",
        ))

    def reset_cursors(self) -> None:
        """Clear tick cursors. Call after MT5 reconnect to re-bootstrap."""
        self._tick_cursors.clear()
        logger.info("strategy.cursors_reset")

    async def on_config_changed(self, name: str) -> None:
        """Called when a config file changes. Reload plans if trade_plans changed."""
        logger.info("strategy.config_changed", file=name)
        if name == "trade_plans":
            await rule_engine.load_plans()


# Global instance
strategy_engine = StrategyEngine()
