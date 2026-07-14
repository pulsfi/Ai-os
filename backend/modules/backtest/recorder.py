"""MarketRecorder — the rolling historical window behind backtesting.

Persists two streams into SQLite (WAL, same pattern as the bot ledger):

* price samples: (mint, ts, price) — every market-cap observation the
  sniper makes (stream marks and REST sweeps), throttled to one write
  per mint per SAMPLE_MIN_GAP_S.
* launch snapshots: the features the strategy saw at decision time
  (score, approved, mcap, buyers, holder concentration when checked).

Retention is a rolling window (default 5 days) pruned on write. Candles
(1m/5m/15m) are aggregated at read time from the raw samples — honest
OHLCV over what was actually observed, never interpolated.
"""

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from config import Settings

logger = logging.getLogger(__name__)

SAMPLE_MIN_GAP_S = 10.0
TIMEFRAMES_S = {"1m": 60, "5m": 300, "15m": 900}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_samples (
    mint TEXT NOT NULL,
    ts   REAL NOT NULL,          -- unix seconds
    price_usd REAL NOT NULL      -- pump coins: mcap/1e9
);
CREATE INDEX IF NOT EXISTS idx_samples_mint_ts ON price_samples (mint, ts);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON price_samples (ts);

CREATE TABLE IF NOT EXISTS launch_snapshots (
    mint TEXT NOT NULL,
    ts   REAL NOT NULL,
    symbol TEXT NOT NULL,
    score REAL NOT NULL,
    approved INTEGER NOT NULL,
    mcap_usd REAL,
    buyers INTEGER,              -- NULL = breadth unknown at eval time
    top5_holders_pct REAL        -- NULL = not checked
);
CREATE INDEX IF NOT EXISTS idx_snaps_mint ON launch_snapshots (mint);
CREATE INDEX IF NOT EXISTS idx_snaps_ts ON launch_snapshots (ts);
"""


class MarketRecorder:
    """Owns backtest.db; safe to call from the hot path (throttled, and
    every write is wrapped so recording can never break trading)."""

    def __init__(self, db_path: Path, retention_days: float = 5.0) -> None:
        self._db_path = db_path
        self._retention_s = retention_days * 86400
        self._last_write: dict[str, float] = {}
        self._last_prune = 0.0
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info("Market recorder ready (%s, %.0f-day window)", db_path, retention_days)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # -- writes (hot path — never raise) ------------------------------------

    def sample(self, mint: str, price_usd: float | None) -> None:
        if price_usd is None or price_usd <= 0:
            return
        now = time.time()
        if now - self._last_write.get(mint, 0.0) < SAMPLE_MIN_GAP_S:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO price_samples (mint, ts, price_usd) VALUES (?, ?, ?)",
                    (mint, now, price_usd),
                )
            self._last_write[mint] = now
            if len(self._last_write) > 2048:
                self._last_write.clear()
            self._maybe_prune(now)
        except sqlite3.Error as exc:  # recording must never break trading
            logger.debug("recorder.sample failed: %s", exc)

    def snapshot(
        self,
        mint: str,
        symbol: str,
        score: float,
        approved: bool,
        mcap_usd: float | None,
        buyers: int | None = None,
        top5_holders_pct: float | None = None,
    ) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO launch_snapshots
                       (mint, ts, symbol, score, approved, mcap_usd, buyers, top5_holders_pct)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mint, time.time(), symbol, score, int(approved),
                     mcap_usd, buyers, top5_holders_pct),
                )
        except sqlite3.Error as exc:
            logger.debug("recorder.snapshot failed: %s", exc)

    def _maybe_prune(self, now: float) -> None:
        if now - self._last_prune < 3600:
            return
        self._last_prune = now
        cutoff = now - self._retention_s
        with self._connect() as conn:
            conn.execute("DELETE FROM price_samples WHERE ts < ?", (cutoff,))
            conn.execute("DELETE FROM launch_snapshots WHERE ts < ?", (cutoff,))

    # -- reads ---------------------------------------------------------------

    def path(self, mint: str, after_ts: float, horizon_s: float = 1200.0) -> list[tuple[float, float]]:
        """(ts, price) samples for a mint from after_ts forward."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT ts, price_usd FROM price_samples
                   WHERE mint = ? AND ts >= ? AND ts <= ? ORDER BY ts""",
                (mint, after_ts, after_ts + horizon_s),
            ).fetchall()
        return [(r["ts"], r["price_usd"]) for r in rows]

    def candles(self, mint: str, timeframe: str = "1m", limit: int = 500) -> list[dict]:
        """OHLCV-style buckets aggregated from raw samples (volume = sample
        count; on-curve tokens have no external volume feed — reported
        honestly as observations, never fabricated)."""
        tf = TIMEFRAMES_S.get(timeframe, 60)
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT CAST(ts / ? AS INTEGER) * ? AS bucket,
                          MIN(price_usd) AS low, MAX(price_usd) AS high,
                          COUNT(*) AS n,
                          MIN(ts) AS first_ts, MAX(ts) AS last_ts
                   FROM price_samples WHERE mint = ?
                   GROUP BY bucket ORDER BY bucket DESC LIMIT ?""",
                (tf, tf, mint, limit),
            ).fetchall()
            out = []
            for r in rows:
                o = conn.execute(
                    "SELECT price_usd FROM price_samples WHERE mint=? AND ts=?",
                    (mint, r["first_ts"]),
                ).fetchone()
                c = conn.execute(
                    "SELECT price_usd FROM price_samples WHERE mint=? AND ts=?",
                    (mint, r["last_ts"]),
                ).fetchone()
                out.append({
                    "ts": datetime.fromtimestamp(r["bucket"], tz=timezone.utc).isoformat(),
                    "open": o["price_usd"] if o else r["low"],
                    "high": r["high"], "low": r["low"],
                    "close": c["price_usd"] if c else r["high"],
                    "samples": r["n"],
                })
        return list(reversed(out))

    def launches(self, window_days: float = 5.0) -> list[dict]:
        """Evaluated launches (newest snapshot per mint) within the window."""
        cutoff = time.time() - window_days * 86400
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT mint, MAX(ts) AS ts, symbol, score, approved,
                          mcap_usd, buyers, top5_holders_pct
                   FROM launch_snapshots WHERE ts >= ?
                   GROUP BY mint ORDER BY ts""",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]

    def coverage(self) -> dict:
        """How much replayable reality is in the window (the honest answer
        to 'can I trust a backtest yet?')."""
        with self._connect() as conn:
            s = conn.execute(
                """SELECT COUNT(*) AS n, COUNT(DISTINCT mint) AS mints,
                          MIN(ts) AS lo, MAX(ts) AS hi FROM price_samples"""
            ).fetchone()
            l = conn.execute(
                "SELECT COUNT(*) AS n, COUNT(DISTINCT mint) AS mints FROM launch_snapshots"
            ).fetchone()
        hours = ((s["hi"] or 0) - (s["lo"] or 0)) / 3600 if s["n"] else 0.0
        return {
            "samples": s["n"], "sampled_mints": s["mints"],
            "snapshots": l["n"], "evaluated_launches": l["mints"],
            "window_hours": round(hours, 1),
        }


_recorder: MarketRecorder | None = None


def get_recorder(settings: Settings) -> MarketRecorder:
    """Process-wide singleton, same pattern as the other modules."""
    global _recorder
    if _recorder is None:
        db = Path(settings.bots_db_path).parent / "backtest.db"
        _recorder = MarketRecorder(db, retention_days=settings.backtest_retention_days)
    return _recorder
