"""Screener service — scans MT5 symbols against configurable filters."""

import asyncio
from collections.abc import AsyncGenerator

import structlog

from app.config.loader import config_loader
from app.mt5.client import mt5_client
from app.mt5.models import Bar

logger = structlog.get_logger()

# trade_mode values that indicate a symbol is NOT tradeable
_NON_TRADEABLE_MODES = {0, 3}

# Defaults for batching
_DEFAULT_BATCH_SIZE = 50
_DEFAULT_BATCH_DELAY = 0.5  # seconds between batches
_DEFAULT_SYMBOL_TIMEOUT = 10  # seconds per symbol


class ScreenerService:
    """Scans all tradeable MT5 symbols against price/volume/range filters."""

    def _resolve_filters(self, **overrides: float | None) -> dict:
        """Merge query-param overrides with YAML defaults."""
        cfg = config_loader.get("screener").get("filters", {})
        return {
            "price_min": overrides.get("price_min") or cfg.get("price", {}).get("min", 0),
            "price_max": overrides.get("price_max") or cfg.get("price", {}).get("max", float("inf")),
            "volume_min": overrides.get("volume_min") or cfg.get("daily_volume", {}).get("min", 0),
            "range_min": overrides.get("range_min") or cfg.get("daily_range", {}).get("min", 0),
            "range_max": overrides.get("range_max") or cfg.get("daily_range", {}).get("max", float("inf")),
            "lookback_days": int(
                overrides.get("lookback_days")
                or cfg.get("daily_range", {}).get("lookback_days", 3)
            ),
        }

    @staticmethod
    def _check_price(last_price: float, f: dict) -> bool:
        return f["price_min"] <= last_price <= f["price_max"]

    @staticmethod
    def _check_volume(avg_volume: float, f: dict) -> bool:
        return avg_volume >= f["volume_min"]

    @staticmethod
    def _check_daily_range(daily_ranges: list[float], f: dict) -> bool:
        return all(f["range_min"] <= r <= f["range_max"] for r in daily_ranges)

    @staticmethod
    def _apply_filters(last_price: float, avg_volume: float, daily_ranges: list[float], f: dict) -> bool:
        if not ScreenerService._check_price(last_price, f):
            return False
        if not ScreenerService._check_volume(avg_volume, f):
            return False
        if not ScreenerService._check_daily_range(daily_ranges, f):
            return False
        return True

    async def _scan_symbol(self, symbol: str, filters: dict, timeout: float) -> dict | None:
        """Fetch bars for a single symbol, apply filters, return result or None."""
        try:
            bars: list[Bar] = await asyncio.wait_for(
                mt5_client.get_bars(symbol, "D1", filters["lookback_days"]),
                timeout=timeout,
            )
            if not bars:
                return None

            last_price = bars[-1].close
            avg_volume = sum(b.tick_volume for b in bars) / len(bars)
            daily_ranges = [b.high - b.low for b in bars]

            if not self._apply_filters(last_price, avg_volume, daily_ranges, filters):
                return None

            return {
                "symbol": symbol,
                "last_price": round(last_price, 5),
                "avg_volume": round(avg_volume, 0),
                "avg_daily_range": round(sum(daily_ranges) / len(daily_ranges), 5),
            }
        except asyncio.TimeoutError:
            logger.warning("screener.symbol_timeout", symbol=symbol, timeout=timeout)
            return None
        except Exception:
            logger.exception("screener.scan_symbol_error", symbol=symbol)
            return None

    async def _scan_batch(
        self, symbols: list[str], filters: dict, symbol_timeout: float
    ) -> tuple[list[dict], int]:
        """Scan a batch of symbols sequentially. Returns (results, error_count)."""
        results: list[dict] = []
        errors = 0
        for sym in symbols:
            try:
                r = await self._scan_symbol(sym, filters, symbol_timeout)
                if r is not None:
                    results.append(r)
            except Exception:
                errors += 1
                logger.exception("screener.scan_symbol_error", symbol=sym)
        return results, errors

    def _get_scan_config(self, visible_only: bool | None) -> tuple[dict, float, int, float, bool]:
        """Read scan configuration. Returns (filters won't be resolved here), symbol_timeout, batch_size, batch_delay, visible_only."""
        screener_cfg = config_loader.get("screener")
        symbol_timeout = screener_cfg.get("symbol_timeout", _DEFAULT_SYMBOL_TIMEOUT)
        batch_size = screener_cfg.get("batch_size", _DEFAULT_BATCH_SIZE)
        batch_delay = screener_cfg.get("batch_delay", _DEFAULT_BATCH_DELAY)
        if visible_only is None:
            visible_only = screener_cfg.get("visible_only", True)
        return screener_cfg, symbol_timeout, batch_size, batch_delay, visible_only

    async def _get_tradeable_symbols(self, visible_only: bool) -> list[str]:
        """Get the list of tradeable symbol names from MT5."""
        symbols = await mt5_client.get_symbols()
        return [
            s["name"] for s in symbols
            if s.get("name")
            and s.get("trade_mode") not in _NON_TRADEABLE_MODES
            and (not visible_only or s.get("visible"))
        ]

    async def scan(self, visible_only: bool | None = None, **filter_overrides: float | None) -> dict:
        """Scan tradeable symbols (non-streaming). Returns final result dict."""
        _, symbol_timeout, batch_size, batch_delay, visible_only = self._get_scan_config(visible_only)
        filters = self._resolve_filters(**filter_overrides)
        tradeable = await self._get_tradeable_symbols(visible_only)

        total = len(tradeable)
        logger.info("screener.scan_start", total_symbols=total, visible_only=visible_only)

        all_results: list[dict] = []
        total_errors = 0

        for i in range(0, total, batch_size):
            batch = tradeable[i : i + batch_size]
            batch_num = i // batch_size + 1
            batch_count = (total + batch_size - 1) // batch_size

            logger.info("screener.batch_progress", batch=batch_num, total_batches=batch_count)

            results, errors = await self._scan_batch(batch, filters, symbol_timeout)
            all_results.extend(results)
            total_errors += errors

            if i + batch_size < total:
                await asyncio.sleep(batch_delay)

        logger.info("screener.scan_complete", scanned=total, matched=len(all_results), errors=total_errors)

        return {"results": all_results, "scanned": total, "errors": total_errors}

    async def scan_stream(
        self, visible_only: bool | None = None, **filter_overrides: float | None
    ) -> AsyncGenerator[dict, None]:
        """Scan tradeable symbols, yielding progress dicts after each batch.

        Yields:
            {"type": "progress", "batch": N, "total_batches": M, "scanned_so_far": X, "matched_so_far": Y}
            ... (one per batch)
            {"type": "done", "results": [...], "scanned": N, "errors": N, "count": N}
        """
        _, symbol_timeout, batch_size, batch_delay, visible_only = self._get_scan_config(visible_only)
        filters = self._resolve_filters(**filter_overrides)
        tradeable = await self._get_tradeable_symbols(visible_only)

        total = len(tradeable)
        batch_count = max(1, (total + batch_size - 1) // batch_size)

        logger.info("screener.scan_start", total_symbols=total, visible_only=visible_only)

        all_results: list[dict] = []
        total_errors = 0

        for i in range(0, total, batch_size):
            batch = tradeable[i : i + batch_size]
            batch_num = i // batch_size + 1

            results, errors = await self._scan_batch(batch, filters, symbol_timeout)
            all_results.extend(results)
            total_errors += errors

            yield {
                "type": "progress",
                "batch": batch_num,
                "total_batches": batch_count,
                "scanned_so_far": min(i + batch_size, total),
                "total_symbols": total,
                "matched_so_far": len(all_results),
            }

            if i + batch_size < total:
                await asyncio.sleep(batch_delay)

        logger.info("screener.scan_complete", scanned=total, matched=len(all_results), errors=total_errors)

        yield {
            "type": "done",
            "results": all_results,
            "scanned": total,
            "count": len(all_results),
            "errors": total_errors,
        }

    def get_defaults(self) -> dict:
        """Return current YAML defaults so the frontend can pre-populate filters."""
        cfg = config_loader.get("screener").get("filters", {})
        screener_cfg = config_loader.get("screener")
        return {
            "price_min": cfg.get("price", {}).get("min", 0),
            "price_max": cfg.get("price", {}).get("max", float("inf")),
            "volume_min": cfg.get("daily_volume", {}).get("min", 0),
            "range_min": cfg.get("daily_range", {}).get("min", 0),
            "range_max": cfg.get("daily_range", {}).get("max", float("inf")),
            "lookback_days": cfg.get("daily_range", {}).get("lookback_days", 3),
            "visible_only": screener_cfg.get("visible_only", True),
        }


screener_service = ScreenerService()
