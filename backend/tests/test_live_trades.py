"""Live-trade ledger tests — record + on-chain reconciliation (mock RPC)."""

import pytest

from config import Settings
from models.schemas.execution import RecordTradeRequest
from modules.execution.live_ledger import LiveTradeService

SIG = "5" + "x" * 60
WALLET = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


class StubRpc:
    def __init__(self, status: str | None, failed: bool = False) -> None:
        self._status = status
        self._failed = failed
        self.calls = 0

    async def get_signature_status(self, signature: str):
        self.calls += 1
        return self._status, self._failed


def make_service(tmp_path, rpc) -> LiveTradeService:
    settings = Settings(_env_file=None, live_trades_db_path=str(tmp_path / "live.db"))
    return LiveTradeService(settings, rpc)  # type: ignore[arg-type]


def req(**kw) -> RecordTradeRequest:
    base = dict(signature=SIG, wallet=WALLET, mint=MINT, symbol="BONK", side="buy", usd_size=10.0)
    base.update(kw)
    return RecordTradeRequest(**base)


async def test_record_confirms_finalized_trade(tmp_path) -> None:
    svc = make_service(tmp_path, StubRpc("finalized"))
    trade = await svc.record(req())
    assert trade.status == "confirmed"
    assert trade.confirmed_ts is not None
    assert trade.side == "buy"


async def test_record_marks_failed_trade(tmp_path) -> None:
    svc = make_service(tmp_path, StubRpc(None, failed=True))
    trade = await svc.record(req())
    assert trade.status == "failed"


async def test_record_pending_stays_submitted(tmp_path) -> None:
    """Not yet seen on-chain -> stays submitted until a later reconcile."""
    svc = make_service(tmp_path, StubRpc(None))
    trade = await svc.record(req())
    assert trade.status == "submitted"


async def test_list_reconciles_pending(tmp_path) -> None:
    rpc = StubRpc(None)  # first record leaves it submitted
    svc = make_service(tmp_path, rpc)
    await svc.record(req())
    rpc._status = "confirmed"  # now the chain has it
    trades = await svc.list_trades()
    assert trades[0].status == "confirmed"


async def test_record_is_idempotent_on_signature(tmp_path) -> None:
    svc = make_service(tmp_path, StubRpc("confirmed"))
    await svc.record(req())
    await svc.record(req())  # same signature
    trades = await svc.list_trades()
    assert len(trades) == 1


async def test_reconcile_never_raises_on_rpc_error(tmp_path) -> None:
    class BoomRpc:
        async def get_signature_status(self, signature: str):
            raise RuntimeError("rpc down")

    svc = make_service(tmp_path, BoomRpc())
    trade = await svc.record(req())  # must not raise
    assert trade.status == "submitted"
