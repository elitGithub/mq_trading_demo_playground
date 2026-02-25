"""Market data API routes - REST + WebSocket for price data."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.api.websocket import ws_manager
from app.mt5.client import mt5_client
from app.services.market_data_service import market_data_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/tick/{symbol}")
async def get_tick(symbol: str):
    """Get the latest tick for a symbol. Serves from Redis cache, falls back to MT5."""
    cached = await market_data_service.get_cached_tick(symbol)
    if cached:
        return {
            "symbol": symbol,
            "price": {
                "bid": float(cached["bid"]),
                "ask": float(cached["ask"]),
                "last": float(cached.get("last", 0)),
            },
            "time": cached.get("time", ""),
        }
    # Cache miss (cold start before first engine poll) -- fall back to MT5
    tick = await mt5_client.get_tick(symbol)
    if tick is None:
        return {"symbol": symbol, "price": None, "connected": mt5_client.connected}
    return {
        "symbol": symbol,
        "price": {"bid": tick.bid, "ask": tick.ask, "last": tick.last},
        "time": tick.time.isoformat(),
    }


@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str,
    timeframe: str = Query(default="H1"),
    count: int = Query(default=200, le=1000),
):
    """Get OHLCV bars for a symbol."""
    bars = await mt5_client.get_bars(symbol, timeframe, count)
    return {
        "bars": [
            {
                "time": int(b.time.timestamp()),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "tick_volume": b.tick_volume,
            }
            for b in bars
        ]
    }


@router.get("/symbols")
async def get_symbols(
    tradeable: bool = Query(default=True),
    visible_only: bool = Query(default=False),
):
    """Get symbols available from MT5."""
    symbols = await mt5_client.get_symbols()

    def is_tradeable(mode: int | None) -> bool:
        if mode is None:
            return True
        return mode not in (0, 3)

    filtered = []
    for s in symbols:
        if visible_only and not s.get("visible"):
            continue
        if tradeable and not is_tradeable(s.get("trade_mode")):
            continue
        filtered.append(s.get("name"))

    return {
        "symbols": sorted([s for s in filtered if s]),
        "connected": mt5_client.connected,
    }


@router.get("/symbol_info/{symbol}")
async def get_symbol_info(symbol: str):
    """Get trading constraints for a symbol (volume limits, contract size, etc.)."""
    import asyncio

    async with mt5_client._lock:
        info = await asyncio.to_thread(mt5_client._mt5.symbol_info, symbol)
    if info is None:
        return {"symbol": symbol, "found": False}
    return {
        "symbol": symbol,
        "found": True,
        "volume_min": float(info.volume_min),
        "volume_max": float(info.volume_max),
        "volume_step": float(info.volume_step),
        "trade_contract_size": float(info.trade_contract_size),
        "digits": int(info.digits),
        "point": float(info.point),
    }


@router.websocket("/ws/prices")
async def price_stream(ws: WebSocket):
    """WebSocket endpoint for real-time price streaming.

    Prices are pushed by the strategy engine via event bus -> market_data_service.
    This handler only manages subscribe/unsubscribe messages.
    """
    await ws_manager.connect(ws)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            action = msg.get("action")
            symbol = msg.get("symbol", "")

            if action == "subscribe" and symbol:
                ws_manager.subscribe(ws, f"price:{symbol}")
                # Send cached tick immediately so frontend gets instant data
                cached = await market_data_service.get_cached_tick(symbol)
                if cached:
                    await ws.send_text(json.dumps({
                        "type": "tick",
                        "symbol": symbol,
                        "bid": float(cached["bid"]),
                        "ask": float(cached["ask"]),
                        "time": cached.get("time", ""),
                    }))
                else:
                    # Cache miss (cold start) -- fetch directly from MT5
                    tick = await mt5_client.get_tick(symbol)
                    if tick:
                        await ws.send_text(json.dumps({
                            "type": "tick",
                            "symbol": symbol,
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "time": tick.time.isoformat(),
                        }))
            elif action == "unsubscribe" and symbol:
                ws_manager.unsubscribe(ws, f"price:{symbol}")

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(ws)
