"""Async event bus for decoupled component communication."""

import asyncio
from collections import defaultdict
from typing import Callable, Coroutine, Any

import structlog

from app.events.events import Event, EventType

logger = structlog.get_logger()

# Type for async event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async event bus using asyncio queues."""

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)
        logger.debug("event_bus.subscribed", event_type=event_type.value, handler=handler.__name__)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler for an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to the bus."""
        await self._queue.put(event)

    def publish_nowait(self, event: Event) -> None:
        """Publish an event without waiting (fire and forget)."""
        self._queue.put_nowait(event)

    async def _process(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            handlers = self._handlers.get(event.type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception(
                        "event_bus.handler_error",
                        event_type=event.type.value,
                        handler=handler.__name__,
                    )

    async def start(self) -> None:
        """Start the event processing loop."""
        self._running = True
        self._task = asyncio.create_task(self._process())
        logger.info("event_bus.started")

    async def stop(self) -> None:
        """Stop the event processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("event_bus.stopped")


# Global instance
event_bus = EventBus()
