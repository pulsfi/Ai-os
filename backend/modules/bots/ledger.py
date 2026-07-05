"""SQLite ledger for the bot fleet — the single source of paper-trade truth.

Separate from the Node scalper's market.db (that ledger has its own single
writer). This one lives under backend/data/ and is written only by the
BotRunner loops in this process. WAL mode keeps reads non-blocking.

Writes are tiny (<1ms) so methods are synchronous; runners call them
directly from their async loops without measurable event-loop impact.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from models.schemas.bots import BotTrade

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id      TEXT NOT NULL,
    mint        TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    usd_size    REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_ts    TEXT NOT NULL,
    exit_price  REAL,
    exit_ts     TEXT,
    pnl_usd     REAL,
    pnl_pct     REAL,
    status      TEXT NOT NULL DEFAULT 'open',   -- open | closed
    entry_note  TEXT,
    exit_note   TEXT
);
CREATE INDEX IF NOT EXISTS idx_bot_trades_bot ON bot_trades (bot_id, status);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BotLedger:
    """Owns the SQLite file; one instance shared by every bot runner."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info("Bot ledger ready (%s)", db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # -- writes (bot runners only) ----------------------------------------

    def open_trade(
        self,
        bot_id: str,
        mint: str,
        symbol: str,
        usd_size: float,
        entry_price: float,
        entry_note: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO bot_trades
                   (bot_id, mint, symbol, usd_size, entry_price, entry_ts, entry_note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bot_id, mint, symbol, usd_size, entry_price, _now_iso(), entry_note),
            )
            return int(cur.lastrowid or 0)

    def close_trade(self, trade_id: int, exit_price: float, exit_note: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT usd_size, entry_price FROM bot_trades WHERE id = ? AND status = 'open'",
                (trade_id,),
            ).fetchone()
            if row is None:
                logger.warning("close_trade: trade %s not open", trade_id)
                return
            entry_price = row["entry_price"]
            pnl_pct = (
                (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0
            )
            pnl_usd = row["usd_size"] * pnl_pct / 100
            conn.execute(
                """UPDATE bot_trades
                   SET exit_price = ?, exit_ts = ?, pnl_usd = ?, pnl_pct = ?,
                       status = 'closed', exit_note = ?
                   WHERE id = ?""",
                (
                    exit_price,
                    _now_iso(),
                    round(pnl_usd, 4),
                    round(pnl_pct, 2),
                    exit_note,
                    trade_id,
                ),
            )

    # -- reads --------------------------------------------------------------

    def open_trades(self, bot_id: str) -> list[BotTrade]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bot_trades WHERE bot_id = ? AND status = 'open' ORDER BY id",
                (bot_id,),
            ).fetchall()
        return [BotTrade(**dict(r)) for r in rows]

    def trades(self, bot_id: str | None = None, limit: int = 50) -> list[BotTrade]:
        query = "SELECT * FROM bot_trades"
        params: list[object] = []
        if bot_id is not None:
            query += " WHERE bot_id = ?"
            params.append(bot_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [BotTrade(**dict(r)) for r in rows]

    def closed_trades_chrono(self, bot_id: str | None = None) -> list[BotTrade]:
        """Closed trades oldest-first — the input to an equity curve."""
        query = "SELECT * FROM bot_trades WHERE status = 'closed'"
        params: list[object] = []
        if bot_id is not None:
            query += " AND bot_id = ?"
            params.append(bot_id)
        query += " ORDER BY exit_ts, id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [BotTrade(**dict(r)) for r in rows]

    def first_entry_ts(self) -> str | None:
        """Earliest trade entry timestamp across the whole fleet (ISO)."""
        with self._connect() as conn:
            row = conn.execute("SELECT MIN(entry_ts) AS t FROM bot_trades").fetchone()
        return row["t"] if row and row["t"] else None

    def stats(self, bot_id: str) -> dict[str, float | int | None]:
        """open count, closed count, realized PnL, win rate for one bot."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(status = 'open'), 0)  AS open_n,
                          COALESCE(SUM(status = 'closed'), 0) AS closed_n,
                          ROUND(COALESCE(SUM(pnl_usd), 0), 2) AS pnl,
                          COALESCE(SUM(pnl_usd > 0), 0)       AS wins
                   FROM bot_trades WHERE bot_id = ?""",
                (bot_id,),
            ).fetchone()
        closed = row["closed_n"] or 0
        return {
            "open_positions": row["open_n"],
            "closed_trades": closed,
            "realized_pnl_usd": row["pnl"],
            "win_rate_pct": round(row["wins"] / closed * 100, 1) if closed else None,
        }
