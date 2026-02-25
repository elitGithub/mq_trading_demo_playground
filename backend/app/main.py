"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import account, market_data, price_levels, strategy, trading
from app.api.websocket import ws_manager
from app.config.loader import config_loader
from app.config.watcher import ConfigWatcher
from app.data.redis_client import close_redis
from app.events.bus import event_bus
from app.mt5.client import mt5_client
from app.services.market_data_service import market_data_service
from app.strategy.engine import strategy_engine

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger()
config_watcher = ConfigWatcher()


async def mt5_reconnect_loop() -> None:
    """Keep trying to connect to MT5 if the initial attempt fails."""
    delay = 5.0
    while True:
        try:
            if mt5_client.connected:
                await asyncio.sleep(5.0)
                continue

            logger.warning("mt5.reconnect_attempt", delay_seconds=delay)
            connected = await mt5_client.connect()
            if connected:
                logger.info("mt5.reconnected")
                strategy_engine.reset_cursors()
                delay = 5.0
                continue

            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mt5.reconnect_loop_error")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("app.starting")

    # Start event bus
    await event_bus.start()

    # Wire market data service to event bus for WS broadcast
    market_data_service.start_listening()

    # Connect to MT5
    connected = await mt5_client.connect()
    if connected:
        logger.info("app.mt5_connected")
    else:
        logger.warning("app.mt5_not_connected", msg="Will retry in background")

    mt5_reconnect_task = asyncio.create_task(mt5_reconnect_loop())

    # Wire up price level detector reference for the API
    price_levels.set_detector(strategy_engine.level_detector)

    # Start strategy engine
    await strategy_engine.start()

    # Start config file watcher
    await config_watcher.start(on_change=strategy_engine.on_config_changed)

    logger.info("app.started")

    yield

    # Shutdown
    logger.info("app.stopping")
    await config_watcher.stop()
    await strategy_engine.stop()
    await event_bus.stop()
    mt5_reconnect_task.cancel()
    with suppress(asyncio.CancelledError):
        await mt5_reconnect_task
    await mt5_client.disconnect()
    await close_redis()
    logger.info("app.stopped")


app = FastAPI(
    title="Auto Trading System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator(
    should_group_status_codes=False,
    should_group_untemplated=True,
    excluded_handlers=["/metrics"],
).instrument(app, metric_namespace="", metric_subsystem="").expose(app)

# Include routers
app.include_router(market_data.router, prefix="/api")
app.include_router(trading.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(price_levels.router, prefix="/api")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "mt5_connected": mt5_client.connected,
        "strategy_enabled": config_loader.is_strategy_enabled(),
        "ws_connections": ws_manager.active_count,
    }
