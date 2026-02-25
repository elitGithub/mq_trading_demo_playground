"""Price level detection engine - fully config-driven.

All detection parameters are read from config/price_levels.yaml.
No code changes needed to tune the detection algorithms.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import structlog

from app.config.loader import config_loader
from app.mt5.models import Bar

logger = structlog.get_logger()


@dataclass
class PriceLevel:
    """A detected price level (support or resistance zone)."""
    price: float
    zone_upper: float
    zone_lower: float
    level_type: str  # "support" or "resistance"
    timeframe: str
    detection_method: str
    strength: float = 1.0
    touch_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


class PriceLevelDetector:
    """Detects support/resistance levels using config-driven methods."""

    def __init__(self):
        self._levels: dict[str, list[PriceLevel]] = {}  # symbol -> levels

    def _cfg(self, *keys, default=None, symbol: str | None = None):
        """Get price_levels config, checking per-symbol overrides first."""
        if symbol:
            override = config_loader.get_nested(
                "price_levels", "price_levels", "symbol_overrides", symbol, *keys,
                default=None,
            )
            if override is not None:
                return override
        return config_loader.get_nested("price_levels", "price_levels", *keys, default=default)

    def _get_methods(self, symbol: str) -> dict:
        """Get detection methods config merged with per-symbol overrides."""
        base = self._cfg("methods") or {}
        overrides = self._cfg("symbol_overrides", symbol, "methods", default=None) or {}
        if not overrides:
            return base
        # Deep merge: per-method override replaces individual keys
        merged = {}
        for method_name in set(list(base.keys()) + list(overrides.keys())):
            base_method = base.get(method_name, {})
            override_method = overrides.get(method_name, {})
            if isinstance(base_method, dict) and isinstance(override_method, dict):
                merged[method_name] = {**base_method, **override_method}
            else:
                merged[method_name] = override_method if method_name in overrides else base_method
        return merged

    def detect_levels(self, symbol: str, bars: list[Bar], timeframe: str) -> list[PriceLevel]:
        """Run all enabled detection methods and merge results."""
        if len(bars) < 10:
            return []

        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.tick_volume for b in bars], dtype=float)

        levels: list[PriceLevel] = []
        methods = self._get_methods(symbol)

        # Pivot points
        if methods.get("pivot_points", {}).get("enabled", True):
            levels.extend(self._detect_pivots(highs, lows, closes, timeframe, methods["pivot_points"]))

        # Volume profile
        if methods.get("volume_profile", {}).get("enabled", False):
            levels.extend(self._detect_volume_profile(closes, volumes, timeframe, methods["volume_profile"]))

        # Clustering
        if methods.get("clustering", {}).get("enabled", False):
            levels.extend(self._detect_clusters(closes, timeframe, methods["clustering"]))

        # Round numbers
        if methods.get("round_numbers", {}).get("enabled", False):
            levels.extend(self._detect_round_numbers(closes, symbol, timeframe, methods["round_numbers"]))

        # Calculate zone widths
        atr = self._calculate_atr(highs, lows, closes)
        zone_multiplier = self._cfg("zones", "width_atr_multiplier", default=0.5, symbol=symbol)
        zone_width = atr * zone_multiplier

        for level in levels:
            level.zone_upper = level.price + zone_width
            level.zone_lower = level.price - zone_width

        # Score and rank levels
        levels = self._score_levels(levels, closes, symbol=symbol)

        # Limit active levels
        max_levels = self._cfg("zones", "max_active_levels", default=10, symbol=symbol)
        levels.sort(key=lambda l: l.strength, reverse=True)
        levels = levels[:max_levels]

        # Classify as support or resistance
        current_price = closes[-1]
        for level in levels:
            level.level_type = "resistance" if level.price > current_price else "support"

        self._levels[symbol] = levels
        return levels

    def _detect_pivots(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
        timeframe: str, cfg: dict,
    ) -> list[PriceLevel]:
        """Detect swing high/low pivot points."""
        lookback = cfg.get("lookback_periods", 20)
        sensitivity = cfg.get("sensitivity", 3)
        levels = []

        for i in range(sensitivity, len(highs) - sensitivity):
            # Swing high
            if all(highs[i] >= highs[i - j] for j in range(1, sensitivity + 1)) and \
               all(highs[i] >= highs[i + j] for j in range(1, sensitivity + 1)):
                levels.append(PriceLevel(
                    price=float(highs[i]),
                    zone_upper=0, zone_lower=0,
                    level_type="resistance",
                    timeframe=timeframe,
                    detection_method="pivot_high",
                ))

            # Swing low
            if all(lows[i] <= lows[i - j] for j in range(1, sensitivity + 1)) and \
               all(lows[i] <= lows[i + j] for j in range(1, sensitivity + 1)):
                levels.append(PriceLevel(
                    price=float(lows[i]),
                    zone_upper=0, zone_lower=0,
                    level_type="support",
                    timeframe=timeframe,
                    detection_method="pivot_low",
                ))

        # Merge nearby levels and count touches
        min_touches = cfg.get("min_touches", 2)
        merged = self._merge_nearby(levels, highs, lows, closes)
        return [l for l in merged if l.touch_count >= min_touches]

    def _detect_volume_profile(
        self, closes: np.ndarray, volumes: np.ndarray, timeframe: str, cfg: dict,
    ) -> list[PriceLevel]:
        """Detect high volume nodes from volume profile."""
        lookback = cfg.get("lookback_bars", 500)
        num_bins = cfg.get("num_bins", 100)
        hvn_threshold = cfg.get("hvn_threshold", 1.5)

        closes = closes[-lookback:]
        volumes = volumes[-lookback:]

        if len(closes) < 50:
            return []

        price_min, price_max = closes.min(), closes.max()
        bins = np.linspace(price_min, price_max, num_bins + 1)
        bin_indices = np.digitize(closes, bins) - 1
        bin_indices = np.clip(bin_indices, 0, num_bins - 1)

        volume_profile = np.zeros(num_bins)
        for i, idx in enumerate(bin_indices):
            volume_profile[idx] += volumes[i]

        mean_vol = volume_profile.mean()
        levels = []

        for i, vol in enumerate(volume_profile):
            if vol > mean_vol * hvn_threshold:
                price = (bins[i] + bins[i + 1]) / 2
                levels.append(PriceLevel(
                    price=float(price),
                    zone_upper=0, zone_lower=0,
                    level_type="support",
                    timeframe=timeframe,
                    detection_method="volume_profile",
                    strength=float(vol / mean_vol),
                ))

        return levels

    def _detect_clusters(
        self, closes: np.ndarray, timeframe: str, cfg: dict,
    ) -> list[PriceLevel]:
        """Detect price clusters using kernel density estimation."""
        try:
            from scipy.signal import argrelextrema
            from scipy.stats import gaussian_kde
        except ImportError:
            return []

        bandwidth = cfg.get("bandwidth", 0.5)
        min_cluster_size = cfg.get("min_cluster_size", 5)

        if len(closes) < 50:
            return []

        kde = gaussian_kde(closes, bw_method=bandwidth)
        price_range = np.linspace(closes.min(), closes.max(), 500)
        density = kde(price_range)

        # Find local maxima in density (= price clusters)
        maxima_idx = argrelextrema(density, np.greater, order=10)[0]

        levels = []
        for idx in maxima_idx:
            price = price_range[idx]
            # Count how many closes are near this price
            nearby = np.sum(np.abs(closes - price) < (closes.std() * 0.1))
            if nearby >= min_cluster_size:
                levels.append(PriceLevel(
                    price=float(price),
                    zone_upper=0, zone_lower=0,
                    level_type="support",
                    timeframe=timeframe,
                    detection_method="clustering",
                    strength=float(density[idx]),
                ))

        return levels

    def _detect_round_numbers(
        self, closes: np.ndarray, symbol: str, timeframe: str, cfg: dict,
    ) -> list[PriceLevel]:
        """Detect round number levels near current price."""
        # Determine interval based on symbol category
        symbols_cfg = config_loader.get("symbols")
        instruments = symbols_cfg.get("symbols", {}).get("instruments", {})
        category = instruments.get(symbol, {}).get("category", "forex_major")

        intervals = cfg.get("intervals", {})
        interval = intervals.get(category, 0.0100)

        current = closes[-1]
        price_range = closes.max() - closes.min()

        levels = []
        base = np.floor(current / interval) * interval

        for i in range(-3, 4):
            price = base + (i * interval)
            if abs(price - current) <= price_range:
                levels.append(PriceLevel(
                    price=float(price),
                    zone_upper=0, zone_lower=0,
                    level_type="support",
                    timeframe=timeframe,
                    detection_method="round_number",
                    strength=1.0,
                ))

        return levels

    def _merge_nearby(
        self, levels: list[PriceLevel],
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    ) -> list[PriceLevel]:
        """Merge levels that are very close together, incrementing touch count."""
        if not levels:
            return []

        atr = self._calculate_atr(highs, lows, closes)
        merge_dist = atr * 0.3

        sorted_levels = sorted(levels, key=lambda l: l.price)
        merged = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            if abs(level.price - merged[-1].price) <= merge_dist:
                merged[-1].touch_count += 1
                merged[-1].price = (merged[-1].price + level.price) / 2
            else:
                merged.append(level)

        return merged

    def _score_levels(self, levels: list[PriceLevel], closes: np.ndarray, symbol: str | None = None) -> list[PriceLevel]:
        """Score levels based on config-driven weights."""
        scoring = self._cfg("scoring", symbol=symbol) or {}
        touch_w = scoring.get("touch_weight", 2.0)
        volume_w = scoring.get("volume_weight", 2.0)

        for level in levels:
            score = level.strength
            score += (level.touch_count - 1) * touch_w
            level.strength = score

        return levels

    @staticmethod
    def _calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(closes) < period + 1:
            return float(highs.max() - lows.min()) * 0.1

        tr_values = []
        for i in range(1, len(closes)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            tr_values.append(max(hl, hc, lc))

        if not tr_values:
            return 0.0

        return float(np.mean(tr_values[-period:]))

    def get_levels(self, symbol: str) -> list[PriceLevel]:
        """Get cached levels for a symbol."""
        return self._levels.get(symbol, [])

    def get_nearby_levels(
        self, symbol: str, price: float, atr: float = 0.0, proximity_atr_multiplier: float = 1.5
    ) -> list[PriceLevel]:
        """Get levels within (ATR * proximity_atr_multiplier) distance of current price."""
        levels = self._levels.get(symbol, [])
        if not levels:
            return []

        proximity_distance = atr * proximity_atr_multiplier if atr > 0 else 0.0

        nearby = []
        for level in levels:
            if not level.is_active:
                continue
            # First check: price is inside the zone bounds
            if level.zone_lower <= price <= level.zone_upper:
                nearby.append(level)
            # Second check: price is within ATR-based proximity distance
            elif proximity_distance > 0 and abs(price - level.price) < proximity_distance:
                nearby.append(level)

        return nearby
