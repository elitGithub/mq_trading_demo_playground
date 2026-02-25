"""Async wrapper around mt5linux RPyC bridge for MetaTrader 5."""

import asyncio
from datetime import datetime, timezone

import structlog

from app.config.settings import settings
from app.mt5.models import (
    AccountInfo, Bar, Order, OrderType, Position, Tick, TradeAction, TradeRequest, TradeResult,
)

logger = structlog.get_logger()


# MT5 copy_ticks flag: all tick types (trade + info)
COPY_TICKS_ALL = 0

# ORDER_FILLING constants for trade requests
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

# SYMBOL_FILLING bitmask bits (from symbol_info.filling_mode)
SYMBOL_FILLING_FOK = 1   # bit 0
SYMBOL_FILLING_IOC = 2   # bit 1


def _resolve_filling_type(filling_mode: int) -> int:
    """Convert symbol_info.filling_mode bitmask to ORDER_FILLING_* constant."""
    mode = int(filling_mode)
    if mode & SYMBOL_FILLING_FOK:
        return ORDER_FILLING_FOK
    if mode & SYMBOL_FILLING_IOC:
        return ORDER_FILLING_IOC
    return ORDER_FILLING_RETURN

# MT5 timeframe mapping
TIMEFRAMES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408, "W1": 32769, "MN1": 49153,
}


class MT5Client:
    """Async client for MetaTrader 5 via mt5linux RPyC bridge."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self._host = host or settings.mt5_host
        self._port = port or settings.mt5_port
        self._mt5 = None
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, timeout: float = 90) -> bool:
        """Connect to the MT5 RPyC bridge and initialize."""
        try:
            from mt5linux import MetaTrader5
            self._mt5 = MetaTrader5(
                host=self._host, port=self._port, timeout=120
            )

            # Shutdown any stale IPC state first
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._mt5.shutdown), timeout=10
                )
            except Exception:
                pass
            await asyncio.sleep(2)

            # Initialize with credentials so MT5 connects to broker
            mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
            init_kwargs: dict = {"timeout": 60000}
            if settings.mt5_login:
                init_kwargs["login"] = settings.mt5_login
                init_kwargs["password"] = settings.mt5_password
                init_kwargs["server"] = settings.mt5_server

            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._mt5.initialize, mt5_path, **init_kwargs
                ),
                timeout=timeout,
            )
            if result:
                self._connected = True
                version = await asyncio.wait_for(
                    asyncio.to_thread(self._mt5.version), timeout=10
                )
                account = await asyncio.wait_for(
                    asyncio.to_thread(self._mt5.account_info), timeout=10
                )
                logger.info(
                    "mt5.connected",
                    version=version,
                    login=account.login if account else None,
                    server=account.server if account else None,
                    balance=account.balance if account else None,
                )
            else:
                error = await asyncio.to_thread(self._mt5.last_error)
                logger.error("mt5.init_failed", error=error)
            return self._connected
        except asyncio.TimeoutError:
            logger.error("mt5.connect_timeout", timeout=timeout)
            self._connected = False
            return False
        except Exception:
            logger.exception("mt5.connect_error")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Shutdown MT5 connection."""
        if self._mt5:
            try:
                await asyncio.to_thread(self._mt5.shutdown)
            except Exception:
                pass
            self._connected = False
            logger.info("mt5.disconnected")

    async def get_tick(self, symbol: str) -> Tick | None:
        """Get the latest tick for a symbol."""
        if not self._connected:
            return None
        try:
            async with self._lock:
                tick = await asyncio.to_thread(self._mt5.symbol_info_tick, symbol)
            if tick is None:
                return None
            return Tick(
                time=datetime.fromtimestamp(tick.time, tz=timezone.utc),
                bid=tick.bid,
                ask=tick.ask,
                last=tick.last,
                volume=tick.volume,
                symbol=symbol,
                time_msc=getattr(tick, "time_msc", 0),
                flags=getattr(tick, "flags", 0),
            )
        except Exception:
            logger.exception("mt5.get_tick_error", symbol=symbol)
            return None

    async def get_ticks_since(
        self, symbol: str, from_msc: int, count: int = 500
    ) -> list[Tick]:
        """Get all ticks since a millisecond timestamp (inclusive)."""
        if not self._connected:
            return []
        try:
            from_dt = datetime.fromtimestamp(from_msc / 1000.0, tz=timezone.utc)
            async with self._lock:
                ticks = await asyncio.to_thread(
                    self._mt5.copy_ticks_from, symbol, from_dt, count, COPY_TICKS_ALL
                )
            if ticks is None or len(ticks) == 0:
                return []
            result = []
            for r in ticks:
                result.append(Tick(
                    time=datetime.fromtimestamp(int(r["time"]), tz=timezone.utc),
                    bid=float(r["bid"]),
                    ask=float(r["ask"]),
                    last=float(r["last"]),
                    volume=float(r["volume"]),
                    symbol=symbol,
                    time_msc=int(r["time_msc"]),
                    flags=int(r["flags"]),
                ))
            return result
        except Exception:
            logger.exception("mt5.get_ticks_since_error", symbol=symbol)
            return []

    async def get_bars(
        self, symbol: str, timeframe: str = "H1", count: int = 200
    ) -> list[Bar]:
        """Get OHLCV bars from MT5."""
        if not self._connected:
            return []
        tf = TIMEFRAMES.get(timeframe)
        if tf is None:
            logger.error("mt5.invalid_timeframe", timeframe=timeframe)
            return []
        try:
            async with self._lock:
                rates = await asyncio.to_thread(
                    self._mt5.copy_rates_from_pos, symbol, tf, 0, count
                )
            if rates is None or len(rates) == 0:
                return []
            bars = []
            for r in rates:
                bars.append(Bar(
                    time=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    tick_volume=int(r["tick_volume"]),
                    spread=int(r["spread"]),
                    real_volume=int(r["real_volume"]),
                ))
            return bars
        except Exception:
            logger.exception("mt5.get_bars_error", symbol=symbol)
            return []

    async def get_account_info(self) -> AccountInfo | None:
        """Get account information."""
        if not self._connected:
            return None
        try:
            async with self._lock:
                info = await asyncio.to_thread(self._mt5.account_info)
            if info is None:
                return None
            return AccountInfo(
                login=info.login,
                balance=info.balance,
                equity=info.equity,
                margin=info.margin,
                margin_free=info.margin_free,
                margin_level=info.margin_level,
                profit=info.profit,
                currency=info.currency,
                leverage=info.leverage,
                server=info.server,
                name=info.name,
                company=info.company,
            )
        except Exception:
            logger.exception("mt5.get_account_error")
            return None

    async def get_symbols(self) -> list[dict]:
        """Get symbol metadata list from MT5."""
        if not self._connected:
            return []
        try:
            async with self._lock:
                symbols = await asyncio.to_thread(self._mt5.symbols_get)
            if symbols is None:
                return []
            result = []
            for s in symbols:
                name = getattr(s, "name", None) or getattr(s, "symbol", None)
                if not name:
                    continue
                result.append({
                    "name": name,
                    "trade_mode": getattr(s, "trade_mode", None),
                    "visible": bool(getattr(s, "visible", False)),
                })
            return result
        except Exception:
            logger.exception("mt5.get_symbols_error")
            return []

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Get open positions, optionally filtered by symbol."""
        if not self._connected:
            return []
        try:
            async with self._lock:
                if symbol:
                    positions = await asyncio.to_thread(
                        self._mt5.positions_get, symbol=symbol
                    )
                else:
                    positions = await asyncio.to_thread(self._mt5.positions_get)
            if positions is None:
                return []
            return [
                Position(
                    ticket=p.ticket,
                    time=datetime.fromtimestamp(p.time, tz=timezone.utc),
                    type=p.type,
                    volume=p.volume,
                    price_open=p.price_open,
                    sl=p.sl,
                    tp=p.tp,
                    price_current=p.price_current,
                    profit=p.profit,
                    symbol=p.symbol,
                    comment=p.comment,
                    magic=p.magic,
                )
                for p in positions
            ]
        except Exception:
            logger.exception("mt5.get_positions_error")
            return []

    async def get_orders(self, symbol: str | None = None) -> list[Order]:
        """Get pending orders."""
        if not self._connected:
            return []
        try:
            async with self._lock:
                if symbol:
                    orders = await asyncio.to_thread(
                        self._mt5.orders_get, symbol=symbol
                    )
                else:
                    orders = await asyncio.to_thread(self._mt5.orders_get)
            if orders is None:
                return []
            return [
                Order(
                    ticket=o.ticket,
                    time_setup=datetime.fromtimestamp(o.time_setup, tz=timezone.utc),
                    type=o.type,
                    volume_current=o.volume_current,
                    price_open=o.price_open,
                    sl=o.sl,
                    tp=o.tp,
                    symbol=o.symbol,
                    comment=o.comment,
                )
                for o in orders
            ]
        except Exception:
            logger.exception("mt5.get_orders_error")
            return []

    async def place_order(self, request: TradeRequest) -> TradeResult:
        """Place a market or pending order."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")

        try:
            async with self._lock:
                # Get symbol info for filling mode
                symbol_info = await asyncio.to_thread(
                    self._mt5.symbol_info, request.symbol
                )
            if symbol_info is None:
                return TradeResult(success=False, comment=f"Symbol {request.symbol} not found")

            # Ensure symbol is visible
            if not symbol_info.visible:
                async with self._lock:
                    await asyncio.to_thread(
                        self._mt5.symbol_select, request.symbol, True
                    )

            order_type = int(OrderType.BUY if request.side == "BUY" else OrderType.SELL)

            # Get current price if not specified
            if request.price is None:
                tick = await self.get_tick(request.symbol)
                if tick is None:
                    return TradeResult(success=False, comment="Cannot get current price")
                price = tick.ask if request.side == "BUY" else tick.bid
            else:
                price = request.price

            trade_request = {
                "action": 1,  # TRADE_ACTION_DEAL (market order)
                "symbol": request.symbol,
                "volume": request.volume,
                "type": order_type,
                "price": price,
                "magic": request.magic,
                "comment": request.comment or "ATS",
                "type_time": 0,  # GTC
                "type_filling": _resolve_filling_type(symbol_info.filling_mode),
            }

            if request.stop_loss:
                trade_request["sl"] = request.stop_loss
            if request.take_profit:
                trade_request["tp"] = request.take_profit

            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, trade_request)

            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009  # TRADE_RETCODE_DONE
            return TradeResult(
                success=success,
                ticket=result.order if success else 0,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.place_order_error")
            return TradeResult(success=False, comment=str(e))

    async def place_limit_order(
        self,
        symbol: str,
        order_type: OrderType,
        price: float,
        volume: float,
        sl: float = 0.0,
        magic: int = 234100,
        comment: str = "",
    ) -> TradeResult:
        """Place a pending limit order (BUY_LIMIT or SELL_LIMIT)."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")
        try:
            async with self._lock:
                symbol_info = await asyncio.to_thread(
                    self._mt5.symbol_info, symbol
                )
            if symbol_info is None:
                return TradeResult(success=False, comment=f"Symbol {symbol} not found")
            if not symbol_info.visible:
                async with self._lock:
                    await asyncio.to_thread(self._mt5.symbol_select, symbol, True)

            request = {
                "action": int(TradeAction.PENDING),
                "symbol": symbol,
                "volume": volume,
                "type": int(order_type),
                "price": price,
                "sl": sl,
                "magic": magic,
                "comment": comment or "ATS-Level",
                "type_time": 0,  # GTC
                "type_filling": _resolve_filling_type(symbol_info.filling_mode),
            }
            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, request)
            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009
            return TradeResult(
                success=success,
                ticket=result.order if success else 0,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.place_limit_order_error")
            return TradeResult(success=False, comment=str(e))

    async def modify_position_sl(
        self, ticket: int, symbol: str, new_sl: float
    ) -> TradeResult:
        """Modify the stop-loss on an open position."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")
        try:
            request = {
                "action": int(TradeAction.SLTP),
                "position": ticket,
                "symbol": symbol,
                "sl": new_sl,
                "tp": 0.0,
            }
            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, request)
            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009
            return TradeResult(
                success=success,
                ticket=ticket,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.modify_sl_error", ticket=ticket)
            return TradeResult(success=False, comment=str(e))

    async def partial_close(
        self, ticket: int, symbol: str, volume: float
    ) -> TradeResult:
        """Partially close a position by opening an opposite market order."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")
        try:
            # Find the position to determine direction
            positions = await self.get_positions(symbol)
            pos = next((p for p in positions if p.ticket == ticket), None)
            if pos is None:
                return TradeResult(
                    success=False, comment=f"Position {ticket} not found"
                )

            close_type = OrderType.SELL if pos.type == 0 else OrderType.BUY

            async with self._lock:
                symbol_info = await asyncio.to_thread(
                    self._mt5.symbol_info, symbol
                )
            if symbol_info is None:
                return TradeResult(success=False, comment=f"Symbol {symbol} not found")

            tick = await self.get_tick(symbol)
            if tick is None:
                return TradeResult(success=False, comment="Cannot get price")

            price = tick.bid if close_type == OrderType.SELL else tick.ask

            request = {
                "action": int(TradeAction.DEAL),
                "symbol": symbol,
                "volume": volume,
                "type": int(close_type),
                "price": price,
                "position": ticket,
                "comment": f"ATS-TP #{ticket}",
                "type_time": 0,
                "type_filling": _resolve_filling_type(symbol_info.filling_mode),
            }
            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, request)
            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009
            return TradeResult(
                success=success,
                ticket=result.order if success else 0,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.partial_close_error", ticket=ticket)
            return TradeResult(success=False, comment=str(e))

    async def cancel_order(self, ticket: int) -> TradeResult:
        """Cancel a pending order by ticket."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")
        try:
            request = {
                "action": int(TradeAction.REMOVE),
                "order": ticket,
            }
            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, request)
            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009
            return TradeResult(
                success=success,
                ticket=ticket,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.cancel_order_error", ticket=ticket)
            return TradeResult(success=False, comment=str(e))

    async def close_position(self, ticket: int) -> TradeResult:
        """Close a position by ticket number (works on both hedging and netting accounts)."""
        if not self._connected:
            return TradeResult(success=False, comment="MT5 not connected")

        try:
            # Find the position
            positions = await self.get_positions()
            pos = next((p for p in positions if p.ticket == ticket), None)
            if pos is None:
                return TradeResult(success=False, comment=f"Position {ticket} not found")

            # Get symbol info for filling mode
            async with self._lock:
                symbol_info = await asyncio.to_thread(
                    self._mt5.symbol_info, pos.symbol
                )
            if symbol_info is None:
                return TradeResult(success=False, comment=f"Symbol {pos.symbol} not found")

            # Get current price
            tick = await self.get_tick(pos.symbol)
            if tick is None:
                return TradeResult(success=False, comment="Cannot get current price")

            # Close by specifying the position ticket
            close_type = int(OrderType.SELL) if pos.type == 0 else int(OrderType.BUY)
            price = tick.bid if pos.type == 0 else tick.ask

            request = {
                "action": 1,  # TRADE_ACTION_DEAL
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "position": ticket,  # critical: tells MT5 to close this position
                "type_time": 0,
                "type_filling": _resolve_filling_type(symbol_info.filling_mode),
                "comment": f"Close #{ticket}",
            }

            async with self._lock:
                result = await asyncio.to_thread(self._mt5.order_send, request)

            if result is None:
                error = await asyncio.to_thread(self._mt5.last_error)
                return TradeResult(success=False, comment=str(error))

            success = result.retcode == 10009
            return TradeResult(
                success=success,
                ticket=result.order if success else 0,
                retcode=result.retcode,
                comment=result.comment,
            )
        except Exception as e:
            logger.exception("mt5.close_position_error", ticket=ticket)
            return TradeResult(success=False, comment=str(e))


# Global instance
mt5_client = MT5Client()
