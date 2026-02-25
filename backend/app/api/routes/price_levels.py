"""Price level API routes."""

from fastapi import APIRouter

from app.strategy.price_levels import PriceLevelDetector

router = APIRouter(prefix="/levels", tags=["levels"])

# Reference to the detector used by the strategy engine
_detector: PriceLevelDetector | None = None


def set_detector(detector: PriceLevelDetector) -> None:
    global _detector
    _detector = detector


@router.get("/{symbol}")
async def get_price_levels(symbol: str):
    """Get detected price levels for a symbol."""
    if _detector is None:
        return {"levels": []}

    levels = _detector.get_levels(symbol)
    return {
        "levels": [
            {
                "price": l.price,
                "zone_upper": l.zone_upper,
                "zone_lower": l.zone_lower,
                "level_type": l.level_type,
                "timeframe": l.timeframe,
                "method": l.detection_method,
                "strength": l.strength,
                "touch_count": l.touch_count,
                "is_active": l.is_active,
            }
            for l in levels
            if l.is_active
        ]
    }
