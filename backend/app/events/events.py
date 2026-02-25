"""Event type definitions for the event-driven architecture."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """All event types in the system."""
    # Market data
    TICK = "tick"
    BAR_CLOSED = "bar_closed"

    # Price levels
    LEVEL_DETECTED = "level_detected"
    LEVEL_HIT = "level_hit"
    LEVEL_INVALIDATED = "level_invalidated"

    # Trading signals
    SIGNAL_GENERATED = "signal_generated"

    # Order lifecycle
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    ORDER_CANCELLED = "order_cancelled"

    # Position
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_MODIFIED = "position_modified"

    # Risk
    RISK_WARNING = "risk_warning"
    RISK_BREACH = "risk_breach"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"

    # Rule engine
    RULE_TRIGGERED = "rule_triggered"
    PLAN_COMPLETE = "plan_complete"

    # System
    CONFIG_CHANGED = "config_changed"
    MT5_CONNECTED = "mt5_connected"
    MT5_DISCONNECTED = "mt5_disconnected"
    ERROR = "error"


@dataclass
class Event:
    """Base event with type, timestamp, and arbitrary payload."""
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
