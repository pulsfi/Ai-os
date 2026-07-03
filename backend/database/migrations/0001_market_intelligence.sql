-- 0001: Market Intelligence schema (tokens, market_snapshots, paper_trades)
-- Applied by: python -m scripts.migrate
-- Matches models/orm/market.py; regenerate via Alembic once it lands.

CREATE TABLE IF NOT EXISTS tokens (
    id          SERIAL PRIMARY KEY,
    mint        VARCHAR(64) NOT NULL UNIQUE,
    symbol      VARCHAR(32),
    name        VARCHAR(128),
    decimals    INTEGER,
    first_seen  TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tokens_mint ON tokens (mint);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id          SERIAL PRIMARY KEY,
    token_id    INTEGER REFERENCES tokens (id),
    ts          TIMESTAMP NOT NULL,
    symbol      VARCHAR(32) NOT NULL,
    mint        VARCHAR(64),
    price_usd   DOUBLE PRECISION,
    change_24h  DOUBLE PRECISION,
    volume_24h  DOUBLE PRECISION,
    liquidity   DOUBLE PRECISION,
    market_cap  DOUBLE PRECISION,
    fdv         DOUBLE PRECISION,
    sources     VARCHAR(128),
    CONSTRAINT uq_snapshot_token_ts UNIQUE (token_id, ts)
);
CREATE INDEX IF NOT EXISTS ix_market_snapshots_ts ON market_snapshots (ts);
CREATE INDEX IF NOT EXISTS ix_market_snapshots_token_id ON market_snapshots (token_id);
CREATE INDEX IF NOT EXISTS ix_market_snapshots_symbol_ts ON market_snapshots (symbol, ts);

CREATE TABLE IF NOT EXISTS paper_trades (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(32) NOT NULL,
    mint        VARCHAR(64),
    usd_size    DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    entry_ts    TIMESTAMP NOT NULL,
    exit_price  DOUBLE PRECISION,
    exit_ts     TIMESTAMP,
    pnl_usd     DOUBLE PRECISION,
    pnl_pct     DOUBLE PRECISION,
    reasoning   TEXT,
    exit_note   TEXT,
    status      VARCHAR(16) NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS ix_paper_trades_entry_ts ON paper_trades (entry_ts);
