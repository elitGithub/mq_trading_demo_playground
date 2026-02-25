"""SQLAlchemy ORM models for TimescaleDB tables."""

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, Integer, String, Text,
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    symbol = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    volume = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    pnl = Column(Float)
    strategy_id = Column(Text)
    mt5_ticket = Column(BigInteger)
    status = Column(Text, default="OPEN")
    open_time = Column(DateTime(timezone=True))
    close_time = Column(DateTime(timezone=True))
    comment = Column(Text)

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')"),
        CheckConstraint("status IN ('OPEN', 'CLOSED', 'CANCELLED')"),
    )


class PriceLevelRecord(Base):
    __tablename__ = "price_levels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    zone_upper = Column(Float, nullable=False)
    zone_lower = Column(Float, nullable=False)
    level_type = Column(Text, nullable=False)
    timeframe = Column(Text, nullable=False)
    detection_method = Column(Text)
    strength = Column(Float, default=1.0)
    touch_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    invalidated_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("level_type IN ('support', 'resistance')"),
    )


class ConfigHistory(Base):
    __tablename__ = "config_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    filename = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    changed_by = Column(Text, default="system")
