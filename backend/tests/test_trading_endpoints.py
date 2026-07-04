"""Paper-trading bridge tests — synthetic SQLite ledger in tmp_path."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_paper_trading
from modules.trading import PaperTradingService

_SCHEMA = """
CREATE TABLE snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, symbol TEXT NOT NULL,
  mint TEXT, price_usd REAL, change_24h REAL, volume_24h REAL,
  liquidity REAL, market_cap REAL, sources TEXT
);
CREATE TABLE paper_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, mint TEXT,
  usd_size REAL NOT NULL, entry_price REAL NOT NULL, entry_ts TEXT NOT NULL,
  exit_price REAL, exit_ts TEXT, pnl_usd REAL, pnl_pct REAL,
  reasoning TEXT, exit_note TEXT, status TEXT NOT NULL DEFAULT 'open'
);
"""


@pytest.fixture()
def ledger_service(tmp_path) -> PaperTradingService:
    db_file = tmp_path / "09 Automation" / "market" / "market.db"
    db_file.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_file)
    conn.executescript(_SCHEMA)
    conn.executemany(
        """INSERT INTO paper_trades
           (symbol, mint, usd_size, entry_price, entry_ts, exit_price, exit_ts,
            pnl_usd, pnl_pct, reasoning, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("WIF", "MintW", 100, 2.0, "2026-07-01T10:00:00Z", 2.4, "2026-07-01T10:30:00Z", 20.0, 20.0, "breakout", "closed"),
            ("BONK", "MintB", 100, 0.00002, "2026-07-02T10:00:00Z", 0.000018, "2026-07-02T11:00:00Z", -10.0, -10.0, "momentum", "closed"),
            ("JUP", "MintJ", 150, 0.5, "2026-07-03T10:00:00Z", None, None, None, None, "trend", "open"),
        ],
    )
    conn.execute(
        "INSERT INTO snapshots (ts, symbol) VALUES ('2026-07-03T10:00:00Z', 'SOL')"
    )
    conn.commit()
    conn.close()

    return PaperTradingService(
        Settings(_env_file=None, vault_path=tmp_path, log_level="WARNING")
    )


@pytest.fixture()
def ledger_client(ledger_service: PaperTradingService, settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_paper_trading] = lambda: ledger_service
    with TestClient(app) as client:
        yield client


def test_summary_computes_track_record(ledger_client: TestClient) -> None:
    res = ledger_client.get("/api/v1/trading/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["total_trades"] == 3
    assert body["open_trades"] == 1
    assert body["closed_trades"] == 2
    assert body["realized_pnl_usd"] == 10.0  # +20 - 10
    assert body["win_rate_pct"] == 50.0
    assert body["snapshots_stored"] == 1


def test_trades_newest_first_and_filterable(ledger_client: TestClient) -> None:
    all_trades = ledger_client.get("/api/v1/trading/trades").json()
    assert [t["symbol"] for t in all_trades] == ["JUP", "BONK", "WIF"]

    open_only = ledger_client.get("/api/v1/trading/trades?status=open").json()
    assert [t["symbol"] for t in open_only] == ["JUP"]
    assert open_only[0]["status"] == "open"

    assert ledger_client.get("/api/v1/trading/trades?status=bogus").status_code == 422


def test_missing_ledger_reports_unavailable(tmp_path, settings: Settings) -> None:
    """No DB file → honest `available: false`, empty trades, no error."""
    service = PaperTradingService(
        Settings(_env_file=None, vault_path=tmp_path, log_level="WARNING")
    )
    app = create_app(settings)
    app.dependency_overrides[get_paper_trading] = lambda: service
    with TestClient(app) as client:
        summary = client.get("/api/v1/trading/summary").json()
        assert summary["available"] is False
        assert summary["total_trades"] == 0
        assert client.get("/api/v1/trading/trades").json() == []


def test_ledger_is_read_only(ledger_service: PaperTradingService) -> None:
    """The service's connection physically cannot write (mode=ro)."""
    conn = ledger_service._connect()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO snapshots (ts, symbol) VALUES ('x', 'y')")
    conn.close()
