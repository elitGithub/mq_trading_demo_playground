"""Pydantic models for MetaTrader 5 data types."""

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel


class OrderType(IntEnum):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5


class TradeAction(IntEnum):
    DEAL = 1
    PENDING = 5
    SLTP = 6
    REMOVE = 4


class Tick(BaseModel):
    time: datetime
    bid: float
    ask: float
    last: float = 0.0
    volume: float = 0.0
    symbol: str = ""
    time_msc: int = 0
    flags: int = 0


class Bar(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread: int = 0
    real_volume: int = 0


class Position(BaseModel):
    ticket: int
    time: datetime
    type: int  # 0=BUY, 1=SELL
    volume: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    price_current: float = 0.0
    profit: float = 0.0
    symbol: str = ""
    comment: str = ""
    magic: int = 0


class Order(BaseModel):
    ticket: int
    time_setup: datetime | None = None
    type: int
    volume_current: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    symbol: str = ""
    comment: str = ""


class AccountInfo(BaseModel):
    login: int = 0
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    margin_free: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    currency: str = "USD"
    leverage: int = 0
    server: str = ""
    name: str = ""
    company: str = ""


class TradeRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    volume: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    comment: str = ""
    magic: int = 234000


class TradeResult(BaseModel):
    success: bool
    ticket: int = 0
    retcode: int = 0
    comment: str = ""


# --- Rule-based trade plan models ---

class RuleConditionModel(BaseModel):
    field: str  # bid, ask, last
    op: str  # >=, <=, >, <, ==
    value: float


class RuleActionModel(BaseModel):
    type: str  # market_buy, market_sell, buy_limit, sell_limit, etc.
    volume: float | None = None
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    comment: str | None = None


class RuleOnFillModel(BaseModel):
    activate: list[str] = []
    deactivate: list[str] = []


class RuleModel(BaseModel):
    active: bool = False
    conditions: list[RuleConditionModel] = []
    actions: list[RuleActionModel] = []
    on_fill: RuleOnFillModel = RuleOnFillModel()


class TradePlanModel(BaseModel):
    enabled: bool = True
    symbol: str
    magic: int = 234200
    rules: dict[str, RuleModel] = {}


class TradePlanState(BaseModel):
    plan_id: str
    enabled: bool
    symbol: str
    magic: int
    rules: dict[str, str] = {}  # rule_id -> "active" | "inactive" | "executed"
    position_tickets: list[int] = []
    order_tickets: list[int] = []


# --- Legacy trade plan models (level_trade) ---

class TradePlanEntry(BaseModel):
    price: float
    volume: float
    order_ticket: int = 0
    position_ticket: int = 0
    filled: bool = False


class TradePlanTP(BaseModel):
    price: float
    close_volume: float
    new_sl: float | None = None
    hit: bool = False


class TradePlanConfig(BaseModel):
    symbol: str
    entries: list[TradePlanEntry]
    stop_loss: float
    take_profits: list[TradePlanTP]
    magic: int = 234100


class TradePlanStatus(BaseModel):
    state: str
    config: TradePlanConfig
    total_pnl: float = 0.0
    message: str = ""
