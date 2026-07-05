"""Helius token-activity tests — canned parsed transactions, no network."""

import httpx
import pytest

from core.exceptions import ConfigurationError, ExternalServiceError
from modules.market.helius import HeliusClient

MINT = "TargetMint111"


def swap_tx(side: str, wallet: str, ts: int) -> dict:
    """A minimal Helius parsed SWAP where `wallet` buys or sells MINT."""
    leg = {"mint": MINT, "userAccount": wallet}
    return {
        "type": "SWAP",
        "timestamp": ts,
        "feePayer": wallet,
        "events": {
            "swap": {
                "tokenOutputs": [leg] if side == "buy" else [],
                "tokenInputs": [leg] if side == "sell" else [],
            }
        },
    }


def client_with(payload: object, status: int = 200) -> HeliusClient:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "api-key" in dict(req.url.params)
        return httpx.Response(status, json=payload)

    return HeliusClient(
        "test-key",
        http=httpx.AsyncClient(
            base_url="https://api.helius.xyz", transport=httpx.MockTransport(handler)
        ),
        min_interval_s=0.0,
    )


async def test_activity_classifies_buys_and_sells() -> None:
    txs = [
        swap_tx("buy", "walletA", 1_000),
        swap_tx("buy", "walletB", 1_030),
        swap_tx("sell", "walletA", 1_060),
        {"type": "TRANSFER", "timestamp": 1_090, "feePayer": "walletC"},
    ]
    activity = await client_with(txs).get_token_activity(MINT)
    assert activity.sampled_txs == 4
    assert activity.swaps == 3
    assert (activity.buys, activity.sells) == (2, 1)
    assert activity.buy_ratio_pct == pytest.approx(66.7)
    assert activity.unique_wallets == 3
    # 4 txs across 90s -> ~2.67/min
    assert activity.txs_per_minute == pytest.approx(2.67, abs=0.01)
    assert activity.first_ts is not None and activity.last_ts is not None


async def test_activity_handles_empty_history() -> None:
    activity = await client_with([]).get_token_activity(MINT)
    assert activity.sampled_txs == 0
    assert activity.buy_ratio_pct is None
    assert activity.txs_per_minute is None


async def test_activity_without_key_is_configuration_error() -> None:
    client = HeliusClient("", min_interval_s=0.0)
    with pytest.raises(ConfigurationError):
        await client.get_token_activity(MINT)
    await client.aclose()


async def test_activity_upstream_error_is_external() -> None:
    with pytest.raises(ExternalServiceError):
        await client_with({"error": "nope"}, status=429).get_token_activity(MINT)
