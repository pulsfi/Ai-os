"""Read-only view over the Node paper-trading ledger (SQLite).

The DB is opened with `mode=ro` so this process physically cannot write
to it — the Node scalper stays the single writer. When the file does not
exist yet the API reports that honestly instead of erroring or faking.

Methods are synchronous on purpose: reads are tiny and FastAPI runs
sync endpoints in its threadpool, so the event loop is never blocked.
"""

import logging
import sqlite3
from pathlib import Path

from config import Settings
from models.schemas.trading import PaperSummary, PaperTrade

logger = logging.getLogger(__name__)


class PaperTradingService:
    """Reads the paper_trades ledger written by the Node scalper."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = (Path(settings.vault_path) / settings.paper_db_path).resolve()

    @property
    def available(self) -> bool:
        return self._db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        # mode=ro: read-only at the SQLite level, not just by convention.
        conn = sqlite3.connect(f"file:{self._db_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def summary(self) -> PaperSummary:
        """Ledger totals — the paper track record at a glance."""
        if not self.available:
            return PaperSummary(available=False)
        with self._connect() as conn:
            trades = conn.execute(
                """SELECT COUNT(*) AS total,
                          COALESCE(SUM(status = 'open'), 0) AS open,
                          COALESCE(SUM(status = 'closed'), 0) AS closed,
                          ROUND(COALESCE(SUM(pnl_usd), 0), 2) AS pnl,
                          COALESCE(SUM(pnl_usd > 0), 0) AS wins,
                          MAX(entry_ts) AS last_entry
                   FROM paper_trades"""
            ).fetchone()
            snaps = conn.execute("SELECT COUNT(*) AS c FROM snapshots").fetchone()
        closed = trades["closed"] or 0
        return PaperSummary(
            available=True,
            total_trades=trades["total"],
            open_trades=trades["open"],
            closed_trades=closed,
            realized_pnl_usd=trades["pnl"],
            win_rate_pct=round(trades["wins"] / closed * 100, 1) if closed else None,
            last_entry_ts=trades["last_entry"],
            snapshots_stored=snaps["c"],
        )

    def trades(self, limit: int = 50, status: str | None = None) -> list[PaperTrade]:
        """Trade log, newest first; optionally filtered to open|closed."""
        if not self.available:
            return []
        query = "SELECT * FROM paper_trades"
        params: list[object] = []
        if status in ("open", "closed"):
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY entry_ts DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [PaperTrade(**dict(row)) for row in rows]


_service: PaperTradingService | None = None


def get_paper_trading_service(settings: Settings) -> PaperTradingService:
    """Process-wide singleton, same pattern as the other modules."""
    global _service
    if _service is None:
        _service = PaperTradingService(settings)
    return _service
