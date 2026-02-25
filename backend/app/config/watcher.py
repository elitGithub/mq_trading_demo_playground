"""File watcher for hot-reloading YAML config files."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from app.config.loader import config_loader

logger = structlog.get_logger()


class ConfigFileHandler(FileSystemEventHandler):
    """Watches for YAML file changes and triggers config reload."""

    def __init__(self, callback: Callable[..., Any] | None = None):
        self._callback = callback
        self._debounce_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".yaml" or path.parent.name == "history":
            return

        name = path.stem
        logger.info("config.file_changed", file=name)
        config_loader.reload(name)

        if self._callback and self._loop:
            self._loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._callback(name),
            )


class ConfigWatcher:
    """Manages the file watcher lifecycle."""

    def __init__(self, config_dir: str | None = None):
        self.config_dir = config_dir or str(config_loader.config_dir)
        self._observer: Observer | None = None
        self._handler = ConfigFileHandler()

    async def start(self, on_change: Callable[..., Any] | None = None) -> None:
        """Start watching the config directory."""
        self._handler._callback = on_change
        self._handler.set_loop(asyncio.get_running_loop())
        self._observer = Observer()
        self._observer.schedule(self._handler, self.config_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("config.watcher.started", dir=self.config_dir)

    async def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("config.watcher.stopped")
