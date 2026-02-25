"""One-shot level-trading plan manager.

Places limit buy orders at predefined price levels with a shared stop-loss
and a two-stage scaled exit (partial closes + trailing SL).

State machine: IDLE -> PLACING -> ACTIVE -> TP1_HIT -> COMPLETE / STOPPED
"""

import asyncio

import structlog

from app.mt5.client import mt5_client
from app.mt5.models import OrderType, TradePlanConfig, TradePlanEntry, TradePlanTP

logger = structlog.get_logger()


class LevelTradeManager:
    """Manages a single level-trading plan lifecycle."""

    STATE_IDLE = "IDLE"
    STATE_PLACING = "PLACING"
    STATE_ACTIVE = "ACTIVE"
    STATE_TP1_HIT = "TP1_HIT"
    STATE_COMPLETE = "COMPLETE"
    STATE_STOPPED = "STOPPED"
    STATE_ERROR = "ERROR"

    def __init__(self):
        self._state: str = self.STATE_IDLE
        self._config: TradePlanConfig | None = None
        self._task: asyncio.Task | None = None
        self._total_pnl: float = 0.0
        self._message: str = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def config(self) -> TradePlanConfig | None:
        return self._config

    @property
    def total_pnl(self) -> float:
        return self._total_pnl

    @property
    def message(self) -> str:
        return self._message

    async def start(self, config: TradePlanConfig) -> bool:
        """Start a new trade plan. Returns False if already running."""
        if self._state not in (
            self.STATE_IDLE, self.STATE_COMPLETE, self.STATE_STOPPED, self.STATE_ERROR
        ):
            return False

        self._config = config
        self._state = self.STATE_PLACING
        self._total_pnl = 0.0
        self._message = ""

        # Reset entry/TP state
        for entry in self._config.entries:
            entry.order_ticket = 0
            entry.position_ticket = 0
            entry.filled = False
        for tp in self._config.take_profits:
            tp.hit = False

        self._task = asyncio.create_task(self._run())
        logger.info("level_trade.started", symbol=config.symbol)
        return True

    async def stop(self) -> None:
        """Cancel the plan: cancel unfilled orders, close open positions."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._config:
            await self._cleanup()

        self._state = self.STATE_STOPPED
        self._message = "Plan cancelled by user"
        logger.info("level_trade.stopped")

    async def _cleanup(self) -> None:
        """Cancel pending orders and close any open positions from this plan."""
        for entry in self._config.entries:
            if entry.order_ticket and not entry.filled:
                await mt5_client.cancel_order(entry.order_ticket)
            if entry.position_ticket:
                positions = await mt5_client.get_positions(self._config.symbol)
                if any(p.ticket == entry.position_ticket for p in positions):
                    await mt5_client.close_position(entry.position_ticket)

    async def _run(self) -> None:
        """Main polling loop."""
        try:
            # Phase 1: Place limit orders
            ok = await self._place_orders()
            if not ok:
                self._state = self.STATE_ERROR
                return

            self._state = self.STATE_ACTIVE
            self._message = "Limit orders placed, waiting for fills"
            logger.info("level_trade.orders_placed")

            # Phase 2: Monitor fills, TPs, and SL
            while self._state in (self.STATE_ACTIVE, self.STATE_TP1_HIT):
                await self._poll()
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("level_trade.run_error")
            self._state = self.STATE_ERROR
            self._message = "Unexpected error in trade plan loop"

    async def _place_orders(self) -> bool:
        """Place all limit buy orders."""
        for entry in self._config.entries:
            result = await mt5_client.place_limit_order(
                symbol=self._config.symbol,
                order_type=OrderType.BUY_LIMIT,
                price=entry.price,
                volume=entry.volume,
                sl=self._config.stop_loss,
                magic=self._config.magic,
                comment=f"MDV-L@{entry.price}",
            )
            if not result.success:
                self._message = f"Failed to place limit at {entry.price}: {result.comment}"
                logger.error(
                    "level_trade.place_failed",
                    price=entry.price, comment=result.comment,
                )
                await self._cleanup()
                return False
            entry.order_ticket = result.ticket
            logger.info(
                "level_trade.order_placed",
                price=entry.price, ticket=result.ticket,
            )
        return True

    async def _poll(self) -> None:
        """Single poll iteration: check fills, prices, and TP/SL conditions."""
        symbol = self._config.symbol
        magic = self._config.magic

        # Check pending orders still alive
        pending_orders = await mt5_client.get_orders(symbol)
        pending_tickets = {o.ticket for o in pending_orders}

        # Check open positions with our magic number
        all_positions = await mt5_client.get_positions(symbol)
        our_positions = [p for p in all_positions if p.magic == magic]
        position_tickets = {p.ticket for p in our_positions}

        # Detect fills: order gone from pending + position appeared
        for entry in self._config.entries:
            if entry.filled:
                continue
            if entry.order_ticket and entry.order_ticket not in pending_tickets:
                # Order is gone -- find the matching position
                for pos in our_positions:
                    if pos.ticket not in {
                        e.position_ticket for e in self._config.entries if e.filled
                    }:
                        if abs(pos.price_open - entry.price) < 0.05:
                            entry.position_ticket = pos.ticket
                            entry.filled = True
                            logger.info(
                                "level_trade.filled",
                                price=entry.price,
                                position_ticket=pos.ticket,
                            )
                            break

        # If no positions at all and no pending orders, SL must have been hit
        filled_entries = [e for e in self._config.entries if e.filled]
        has_pending = any(
            e.order_ticket in pending_tickets
            for e in self._config.entries
            if not e.filled and e.order_ticket
        )
        has_positions = any(
            e.position_ticket in position_tickets for e in filled_entries
        )

        if filled_entries and not has_positions and not has_pending:
            self._state = self.STATE_STOPPED
            self._message = "All positions closed (stop-loss hit)"
            # Cancel any remaining pending orders
            for entry in self._config.entries:
                if not entry.filled and entry.order_ticket in pending_tickets:
                    await mt5_client.cancel_order(entry.order_ticket)
            self._update_pnl(our_positions)
            logger.info("level_trade.stopped_out")
            return

        if not filled_entries:
            return

        # Calculate current P&L
        self._update_pnl(our_positions)

        # Get current price
        tick = await mt5_client.get_tick(symbol)
        if tick is None:
            return
        bid = tick.bid

        # Check TP1
        tp1 = self._config.take_profits[0]
        if not tp1.hit and bid >= tp1.price:
            logger.info("level_trade.tp1_triggered", bid=bid, target=tp1.price)
            await self._execute_tp1(tp1, our_positions)
            return

        # Check TP2 (only after TP1)
        if len(self._config.take_profits) > 1 and tp1.hit:
            tp2 = self._config.take_profits[1]
            if not tp2.hit and bid >= tp2.price:
                logger.info("level_trade.tp2_triggered", bid=bid, target=tp2.price)
                await self._execute_tp2(tp2, our_positions)
                return

    async def _execute_tp1(self, tp: TradePlanTP, positions: list) -> None:
        """Execute TP1: close 300 shares across positions, move SL on remainder."""
        remaining_to_close = tp.close_volume
        symbol = self._config.symbol

        # Sort entries by price descending (close highest-price entry first)
        filled_entries = sorted(
            [e for e in self._config.entries if e.filled],
            key=lambda e: e.price,
            reverse=True,
        )

        for entry in filled_entries:
            if remaining_to_close <= 0:
                break
            # Find this position in current positions list
            pos = next((p for p in positions if p.ticket == entry.position_ticket), None)
            if pos is None:
                continue

            close_vol = min(remaining_to_close, pos.volume)
            if close_vol >= pos.volume:
                # Full close
                result = await mt5_client.close_position(entry.position_ticket)
            else:
                # Partial close
                result = await mt5_client.partial_close(
                    entry.position_ticket, symbol, close_vol
                )
            if result.success:
                remaining_to_close -= close_vol
                logger.info(
                    "level_trade.tp1_closed",
                    ticket=entry.position_ticket, volume=close_vol,
                )
            else:
                logger.error(
                    "level_trade.tp1_close_failed",
                    ticket=entry.position_ticket, comment=result.comment,
                )

        # Move SL to breakeven+ on remaining positions
        if tp.new_sl:
            remaining_positions = await mt5_client.get_positions(symbol)
            for pos in remaining_positions:
                if pos.magic == self._config.magic:
                    result = await mt5_client.modify_position_sl(
                        pos.ticket, symbol, tp.new_sl
                    )
                    if result.success:
                        logger.info(
                            "level_trade.sl_moved",
                            ticket=pos.ticket, new_sl=tp.new_sl,
                        )

        tp.hit = True
        self._state = self.STATE_TP1_HIT
        self._message = f"TP1 hit at {tp.price}, SL moved to {tp.new_sl}"

        # Cancel any remaining unfilled limit orders
        pending_orders = await mt5_client.get_orders(symbol)
        pending_tickets = {o.ticket for o in pending_orders}
        for entry in self._config.entries:
            if not entry.filled and entry.order_ticket in pending_tickets:
                await mt5_client.cancel_order(entry.order_ticket)

    async def _execute_tp2(self, tp: TradePlanTP, positions: list) -> None:
        """Execute TP2: close all remaining shares."""
        symbol = self._config.symbol
        remaining_positions = await mt5_client.get_positions(symbol)
        for pos in remaining_positions:
            if pos.magic == self._config.magic:
                result = await mt5_client.close_position(pos.ticket)
                if result.success:
                    logger.info("level_trade.tp2_closed", ticket=pos.ticket)

        tp.hit = True
        self._state = self.STATE_COMPLETE
        self._message = f"TP2 hit at {tp.price}, plan complete"
        logger.info("level_trade.complete")

    def _update_pnl(self, positions: list) -> None:
        self._total_pnl = sum(
            p.profit for p in positions if p.magic == self._config.magic
        )


# Global instance
level_trade_manager = LevelTradeManager()
