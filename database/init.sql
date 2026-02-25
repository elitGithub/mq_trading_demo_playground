-- =============================================================================
-- Auto Trading System - TimescaleDB Schema
-- =============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================================================
-- Ticks (raw tick data)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ticks (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    bid         DOUBLE PRECISION NOT NULL,
    ask         DOUBLE PRECISION NOT NULL,
    last        DOUBLE PRECISION,
    volume      DOUBLE PRECISION DEFAULT 0
);

SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks (symbol, time DESC);

-- Compression policy: compress chunks older than 7 days
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('ticks', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy: drop data older than 90 days (adjust as needed)
SELECT add_retention_policy('ticks', INTERVAL '90 days', if_not_exists => TRUE);

-- =============================================================================
-- Continuous Aggregation: 1-minute OHLCV
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    first(bid, time) AS open,
    max(bid) AS high,
    min(bid) AS low,
    last(bid, time) AS close,
    count(*) AS tick_count
FROM ticks
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('ohlcv_1m',
    start_offset    => INTERVAL '1 hour',
    end_offset      => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists   => TRUE
);

-- =============================================================================
-- Continuous Aggregation: 5-minute OHLCV
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    first(bid, time) AS open,
    max(bid) AS high,
    min(bid) AS low,
    last(bid, time) AS close,
    count(*) AS tick_count
FROM ticks
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('ohlcv_5m',
    start_offset    => INTERVAL '2 hours',
    end_offset      => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists   => TRUE
);

-- =============================================================================
-- Continuous Aggregation: 1-hour OHLCV
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    first(bid, time) AS open,
    max(bid) AS high,
    min(bid) AS low,
    last(bid, time) AS close,
    count(*) AS tick_count
FROM ticks
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset    => INTERVAL '1 day',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists   => TRUE
);

-- =============================================================================
-- Trade Log
-- =============================================================================
CREATE TABLE IF NOT EXISTS trades (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    volume          DOUBLE PRECISION NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    exit_price      DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    take_profit     DOUBLE PRECISION,
    pnl             DOUBLE PRECISION,
    strategy_id     TEXT,
    mt5_ticket      BIGINT,
    status          TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    open_time       TIMESTAMPTZ,
    close_time      TIMESTAMPTZ,
    comment         TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades (time DESC);

-- =============================================================================
-- Price Levels
-- =============================================================================
CREATE TABLE IF NOT EXISTS price_levels (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    zone_upper      DOUBLE PRECISION NOT NULL,
    zone_lower      DOUBLE PRECISION NOT NULL,
    level_type      TEXT NOT NULL CHECK (level_type IN ('support', 'resistance')),
    timeframe       TEXT NOT NULL,
    detection_method TEXT,
    strength        DOUBLE PRECISION DEFAULT 1.0,
    touch_count     INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    invalidated_at  TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_levels_symbol_active ON price_levels (symbol, is_active);

-- =============================================================================
-- Config History (audit trail)
-- =============================================================================
CREATE TABLE IF NOT EXISTS config_history (
    id              BIGSERIAL PRIMARY KEY,
    filename        TEXT NOT NULL,
    content         TEXT NOT NULL,
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    changed_by      TEXT DEFAULT 'system'
);

-- =============================================================================
-- Equity Snapshots
-- =============================================================================
CREATE TABLE IF NOT EXISTS equity_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    balance         DOUBLE PRECISION,
    equity          DOUBLE PRECISION,
    margin          DOUBLE PRECISION,
    free_margin     DOUBLE PRECISION,
    open_positions  INTEGER DEFAULT 0,
    daily_pnl       DOUBLE PRECISION DEFAULT 0
);

SELECT create_hypertable('equity_snapshots', 'time', if_not_exists => TRUE);
