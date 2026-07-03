"""RpcClient behavior: parsing, retry, failover, protocol errors.

All tests run against httpx.MockTransport — no network, deterministic.
"""

import httpx
import pytest

from modules.solana.client import RpcClient, SolanaRpcError


def make_client(handler, endpoints: str | list[str] = "http://rpc.test") -> RpcClient:
    """RpcClient wired to a fake transport."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RpcClient(endpoints, http=http, max_retries=1)


def rpc_ok(result) -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})


async def test_get_slot_parses_result() -> None:
    """A plain result round-trips through the typed method."""
    client = make_client(lambda req: rpc_ok(123_456))
    assert await client.get_slot() == 123_456


async def test_protocol_error_raises_without_retry() -> None:
    """JSON-RPC errors are answers — surfaced once, never retried."""
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "nope"}})

    client = make_client(handler)
    with pytest.raises(SolanaRpcError, match="nope"):
        await client.get_slot()
    assert calls == 1  # no retry on protocol errors


async def test_transient_500_is_retried_then_succeeds() -> None:
    """5xx responses retry with backoff and recover."""
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500) if calls == 1 else rpc_ok(7)

    client = make_client(handler)
    assert await client.get_slot() == 7
    assert calls == 2


async def test_failover_to_second_endpoint() -> None:
    """When the primary endpoint is unreachable, the fallback serves."""

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "primary.test":
            raise httpx.ConnectError("refused", request=req)
        return rpc_ok(42)

    client = make_client(handler, endpoints=["http://primary.test", "http://fallback.test"])
    assert await client.get_slot() == 42


async def test_all_endpoints_exhausted_raises() -> None:
    """Total failure surfaces as SolanaRpcError, not a raw httpx exception."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    client = make_client(handler)
    with pytest.raises(SolanaRpcError, match="failed on all endpoints"):
        await client.get_slot()


async def test_token_authorities_revoked_detection() -> None:
    """Revoked authorities (both None) => is_fully_revoked True."""
    payload = {"value": {"data": {"parsed": {"info": {"mintAuthority": None, "freezeAuthority": None}}}}}
    client = make_client(lambda req: rpc_ok(payload))
    auth = await client.get_token_authorities("SomeMint")
    assert auth.is_fully_revoked is True


async def test_token_authorities_live_mint_flagged() -> None:
    """A live mint authority must be reported (the rug signal)."""
    payload = {"value": {"data": {"parsed": {"info": {"mintAuthority": "Attacker111", "freezeAuthority": None}}}}}
    client = make_client(lambda req: rpc_ok(payload))
    auth = await client.get_token_authorities("SomeMint")
    assert auth.mint_authority == "Attacker111"
    assert auth.is_fully_revoked is False


async def test_chain_status_degrades_instead_of_raising() -> None:
    """If every sub-probe fails, status still assembles as unhealthy."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    client = make_client(handler)
    status = await client.get_chain_status()
    assert status.healthy is False
    assert status.slot is None and status.epoch is None
