"""WebSocket connection manager for real-time price streaming."""

import asyncio
import json

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class ConnectionManager:
    """Manages active WebSocket connections and topic subscriptions."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}  # topic -> connections
        self._all: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._all.add(ws)
        logger.info("ws.connected", total=len(self._all))

    def disconnect(self, ws: WebSocket) -> None:
        self._all.discard(ws)
        for topic, conns in self._connections.items():
            conns.discard(ws)
        logger.info("ws.disconnected", total=len(self._all))

    def subscribe(self, ws: WebSocket, topic: str) -> None:
        if topic not in self._connections:
            self._connections[topic] = set()
        self._connections[topic].add(ws)

    def unsubscribe(self, ws: WebSocket, topic: str) -> None:
        if topic in self._connections:
            self._connections[topic].discard(ws)

    async def broadcast(self, topic: str, data: dict) -> None:
        """Send data to all connections subscribed to a topic."""
        conns = self._connections.get(topic, set())
        dead = set()
        message = json.dumps(data)
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_all(self, data: dict) -> None:
        """Send data to all connected clients."""
        dead = set()
        message = json.dumps(data)
        for ws in self._all:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._all)


# Global instance
ws_manager = ConnectionManager()
