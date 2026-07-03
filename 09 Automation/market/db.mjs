// Market Database — SQLite via Node's built-in node:sqlite (Step 3 of the roadmap)
import { DatabaseSync } from "node:sqlite";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DB_PATH = join(dirname(fileURLToPath(import.meta.url)), "market.db");

export function openDb() {
  const db = new DatabaseSync(DB_PATH);
  db.exec(`
    CREATE TABLE IF NOT EXISTS snapshots (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      ts          TEXT NOT NULL,           -- ISO timestamp
      symbol      TEXT NOT NULL,
      mint        TEXT,
      price_usd   REAL,
      change_24h  REAL,
      volume_24h  REAL,
      liquidity   REAL,
      market_cap  REAL,
      sources     TEXT                     -- which APIs contributed
    );
    CREATE INDEX IF NOT EXISTS idx_snap_symbol_ts ON snapshots(symbol, ts);

    CREATE TABLE IF NOT EXISTS paper_trades (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol      TEXT NOT NULL,
      mint        TEXT,
      usd_size    REAL NOT NULL,           -- position size in USD (hypothetical)
      entry_price REAL NOT NULL,
      entry_ts    TEXT NOT NULL,
      exit_price  REAL,
      exit_ts     TEXT,
      pnl_usd     REAL,
      pnl_pct     REAL,
      reasoning   TEXT,
      exit_note   TEXT,
      status      TEXT NOT NULL DEFAULT 'open'  -- open | closed
    );
  `);
  return db;
}

export function insertSnapshot(db, s) {
  db.prepare(
    `INSERT INTO snapshots (ts, symbol, mint, price_usd, change_24h, volume_24h, liquidity, market_cap, sources)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(s.ts, s.symbol, s.mint, s.price, s.change24h, s.volume24h, s.liquidity, s.marketCap, s.sources);
}

export function dbStats(db) {
  const snaps = db.prepare("SELECT COUNT(*) c, COUNT(DISTINCT substr(ts,1,10)) d FROM snapshots").get();
  const trades = db.prepare(
    "SELECT COUNT(*) total, SUM(status='open') open, ROUND(SUM(COALESCE(pnl_usd,0)),2) pnl FROM paper_trades",
  ).get();
  return { snapshots: snaps.c, days: snaps.d, trades: trades.total, openTrades: trades.open ?? 0, totalPnl: trades.pnl ?? 0 };
}
