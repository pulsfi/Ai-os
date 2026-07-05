"""Manual (Phantom-signed) swap builder tests.

Safety invariants under test: the builder returns only an UNSIGNED
base64 tx (never signs), the kill switch halts building, the buy cap
blocks fat-finger sizes, and a sell of nothing is refused. Jupiter + RPC
are mocked; no network, no keys.
"""

import base64
from datetime import datetime, timezone

import httpx
import pytest

from config import Settings
from models.schemas.execution import RiskLimits
from modules.execution.manual_swap import ManualSwapBuilder, ManualTradeBlocked
from modules.execution.risk_engine import RiskEngine

USER = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"

# A well-formed base64 stand-in for Jupiter's serialized transaction.
_FAKE_TX_B64 = base64.b64encode(b"unsigned-transaction-bytes").decode()


def make_risk(kill: bool = False) -> RiskEngine:
    engine = RiskEngine(
        limits=RiskLimits(
            max_position_usd=10.0,
            daily_loss_limit_usd=25.0,
            max_concurrent_positions=2,
            max_slippage_bps=150,
        ),
        armed=False,
    )
    engine.set_kill_switch(kill)
    return engine


class FakeMarket:
    def __init__(self, sol_price: float | None = 200.0) -> None:
        self._price = sol_price

    async def get_watchlist(self):
        from modules.market.market_models import TokenMarketData

        return [
            TokenMarketData(
                mint="So11111111111111111111111111111111111111112",
                symbol="SOL",
                price_usd=self._price,
                change_24h=None, volume_24h=None, liquidity_usd=None,
                market_cap=None, fdv=None, sources=["test"],
                fetched_at=datetime.now(timezone.utc),
            )
        ]


class FakeRpc:
    def __init__(self, token_raw: int = 0, decimals: int = 6) -> None:
        self._raw = token_raw
        self._decimals = decimals

    async def get_token_balance_raw(self, owner: str, mint: str) -> tuple[int, int]:
        return self._raw, self._decimals


def builder(
    risk: RiskEngine,
    *,
    quote_ok: bool = True,
    swap_ok: bool = True,
    rpc_raw: int = 0,
    sol_price: float | None = 200.0,
    settings: Settings | None = None,
) -> ManualSwapBuilder:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/quote"):
            if not quote_ok:
                return httpx.Response(400, json={})
            return httpx.Response(
                200, json={"outAmount": "123456789", "priceImpactPct": "0.02"}
            )
        # /swap
        if not swap_ok:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"swapTransaction": _FAKE_TX_B64})

    return ManualSwapBuilder(
        risk,
        FakeRpc(rpc_raw),  # type: ignore[arg-type]
        FakeMarket(sol_price),  # type: ignore[arg-type]
        settings or Settings(_env_file=None),
        http=httpx.AsyncClient(
            base_url="https://quote-api.jup.ag", transport=httpx.MockTransport(handler)
        ),
    )


# --- buy ----------------------------------------------------------------------


async def test_build_buy_returns_unsigned_tx() -> None:
    swap = await builder(make_risk()).build_buy(USER, MINT, 5.0)
    assert swap.swap_transaction_b64 == _FAKE_TX_B64
    # It really is decodable base64 and NOT signed by us (we never touch a key).
    assert base64.b64decode(swap.swap_transaction_b64) == b"unsigned-transaction-bytes"
    assert swap.price_impact_pct == pytest.approx(2.0)
    assert "your key" in swap.warning.lower()


async def test_build_buy_kill_switch_blocks() -> None:
    with pytest.raises(ManualTradeBlocked, match="kill switch"):
        await builder(make_risk(kill=True)).build_buy(USER, MINT, 5.0)


async def test_build_buy_cap_blocks_fat_finger() -> None:
    settings = Settings(_env_file=None, manual_trade_max_usd=50.0)
    with pytest.raises(ManualTradeBlocked, match="exceeds"):
        await builder(make_risk(), settings=settings).build_buy(USER, MINT, 51.0)


async def test_build_buy_no_route_errors() -> None:
    from core.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        await builder(make_risk(), quote_ok=False).build_buy(USER, MINT, 5.0)


# --- sell ---------------------------------------------------------------------


async def test_build_sell_full_balance() -> None:
    swap = await builder(make_risk(), rpc_raw=5_000_000).build_sell(USER, MINT)
    assert swap.swap_transaction_b64 == _FAKE_TX_B64
    assert "Sell full balance" in swap.description


async def test_build_sell_with_no_holdings_refused() -> None:
    with pytest.raises(ManualTradeBlocked, match="holds none"):
        await builder(make_risk(), rpc_raw=0).build_sell(USER, MINT)


async def test_build_sell_kill_switch_blocks() -> None:
    with pytest.raises(ManualTradeBlocked, match="kill switch"):
        await builder(make_risk(kill=True), rpc_raw=5_000_000).build_sell(USER, MINT)
