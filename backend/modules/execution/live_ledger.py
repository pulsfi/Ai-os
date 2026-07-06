"""Live-trade ledger — records REAL wallet trades and reconciles them.

When the user approves a swap in Phantom, the frontend gets a signature
and sends it here. We store the trade (status=submitted) and then confirm
it against the chain via RPC (getSignatureStatuses): confirmed when it
finalizes, failed when it lands with an error. This is the honest record
of real money moved — separate from the paper bot ledger, and it only
ever READS the chain (no signing).
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from models.schemas.execution import LiveTrade, RecordTradeRequest
from modules.solana import RpcClient

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    signature    TEXT NOT NULL UNIQUE,
    wallet       TEXT NOT NULL,
    mint         TEXT NOT NULL,
    symbol       TEXT NOT NULL DEFAULT '',
    side         TEXT NOT NULL,
    usd_size     REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'submitted',  -- submitted|confirmed|failed
    submitted_ts TEXT NOT NULL,
    confirmed_ts TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LiveTradeService:
    """SQLite record of real wallet trades + on-chain reconciliation."""

    def __init__(self, settings: Settings, rpc: RpcClient) -> None:
        self._db_path = Path(settings.live_trades_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._rpc = rpc
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _row(self, r: sqlite3.Row) -> LiveTrade:
        return LiveTrade(**dict(r))

    async def record(self, req: RecordTradeRequest) -> LiveTrade:
        """Store a submitted trade, then try an immediate confirmation."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO live_trades
                   (signature, wallet, mint, symbol, side, usd_size, submitted_ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (req.signature, req.wallet, req.mint, req.symbol, req.side,
                 req.usd_size, _now()),
            )
        await self._reconcile_one(req.signature)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM live_trades WHERE signature = ?", (req.signature,)
            ).fetchone()
        return self._row(row)

    async def _reconcile_one(self, signature: str) -> None:
        try:
            status, failed = await self._rpc.get_signature_status(signature)
        except Exception as exc:  # noqa: BLE001 — reconciliation must never raise up
            logger.warning("reconcile %s failed: %s", signature[:8], exc)
            return
        new_status: str | None = None
        if failed:
            new_status = "failed"
        elif status in ("confirmed", "finalized"):
            new_status = "confirmed"
        if new_status:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE live_trades SET status = ?, confirmed_ts = ? "
                    "WHERE signature = ? AND status = 'submitted'",
                    (new_status, _now(), signature),
                )

    async def list_trades(self, limit: int = 50) -> list[LiveTrade]:
        """Recent real trades, newest first — reconciles any still pending."""
        with self._connect() as conn:
            pending = [
                r["signature"]
                for r in conn.execute(
                    "SELECT signature FROM live_trades WHERE status = 'submitted' "
                    "ORDER BY id DESC LIMIT 20"
                ).fetchall()
            ]
        for sig in pending:
            await self._reconcile_one(sig)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM live_trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(r) for r in rows]


_service: LiveTradeService | None = None


def get_live_trade_service(settings: Settings, rpc: RpcClient) -> LiveTradeService:
    """Process-wide singleton, same pattern as the other modules."""
    global _service
    if _service is None:
        _service = LiveTradeService(settings, rpc)
    return _service
