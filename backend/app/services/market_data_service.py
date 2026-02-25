"""Market data service - data ingestion and caching."""

import structlog

from app.api.websocket import ws_manager
from app.data.redis_client import get_redis
from app.events.bus import event_bus
from app.events.events import Event, EventType
from app.mt5.models import Tick

logger = structlog.get_logger()


class MarketDataService:
    """Handles price data caching in Redis and WS broadcast via events."""

    async def cache_tick(self, tick: Tick) -> None:
        """Cache the latest tick in Redis."""
        r = await get_redis()
        key = f"tick:{tick.symbol}"
        await r.hset(key, mapping={
            "bid": str(tick.bid),
            "ask": str(tick.ask),
            "last": str(tick.last),
            "time": tick.time.isoformat(),
            "time_msc": str(tick.time_msc),
        })

    async def get_cached_tick(self, symbol: str) -> dict | None:
        """Get a cached tick from Redis."""
        r = await get_redis()
        data = await r.hgetall(f"tick:{symbol}")
        return data if data else None

    async def handle_tick_event(self, event: Event) -> None:
        """Broadcast tick data to subscribed WebSocket clients."""
        data = event.data
        symbol = data.get("symbol", "")
        if not symbol:
            return
        await ws_manager.broadcast(f"price:{symbol}", {
            "type": "tick",
            "symbol": symbol,
            "bid": data.get("bid"),
            "ask": data.get("ask"),
            "time": data.get("time"),
        })

    def start_listening(self) -> None:
        """Subscribe to TICK events on the event bus."""
        event_bus.subscribe(EventType.TICK, self.handle_tick_event)
        logger.info("market_data_service.listening")


market_data_service = MarketDataService()
