"""Async Solana JSON-RPC client — the single chain-access point.

This module ends the 4x duplication of the ad-hoc `rpc()` helper in the
Node layer: every future chain call goes through `RpcClient`.

Guarantees:
- READ-ONLY by design: no signing, no keys, no transaction methods exist.
- Retries transient failures (transport errors, 429, 5xx) with backoff.
- Fails over across endpoints (e.g. Helius -> public) before giving up.
- JSON-RPC protocol errors are NOT retried — they are real answers.

Usage (always via DI in app code; standalone use gets a context manager):

    async with RpcClient("https://api.mainnet-beta.solana.com") as rpc:
        slot = await rpc.get_slot()
"""

import asyncio
import logging
from typing import Any

import httpx

from config import Settings
from core.exceptions import ExternalServiceError
from models.schemas.solana import ChainStatus, EpochInfo, TokenAuthorities, TokenSupply

logger = logging.getLogger(__name__)

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
DEFAULT_TIMEOUT_S = 5.0


class SolanaRpcError(ExternalServiceError):
    """A Solana RPC call failed after retries, or the node returned an error."""

    code = "solana_rpc_error"


class RpcClient:
    """Typed async client over Solana JSON-RPC with retry and failover."""

    def __init__(
        self,
        endpoints: str | list[str],
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = 2,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Args:
            endpoints: one URL or an ordered failover list (first = preferred).
            timeout: per-request timeout in seconds.
            max_retries: transient-failure retries per endpoint.
            http: injected client (tests pass a MockTransport-backed one);
                  when omitted the client owns and closes its own.
        """
        self._endpoints = [endpoints] if isinstance(endpoints, str) else list(endpoints)
        self._timeout = timeout
        self._max_retries = max_retries
        self._http = http
        self._owns_http = http is None

    # --- lifecycle -------------------------------------------------------

    async def __aenter__(self) -> "RpcClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazily create the owned HTTP client on first use."""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self._http

    async def aclose(self) -> None:
        """Release the underlying HTTP client (owned clients only)."""
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # --- transport -------------------------------------------------------

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        """Execute one JSON-RPC method with retry + failover.

        Raises:
            SolanaRpcError: node returned a JSON-RPC error, or every
                endpoint/retry failed on transport.
        """
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        last_exc: Exception | None = None

        for endpoint in self._endpoints:
            for attempt in range(self._max_retries + 1):
                try:
                    res = await self._client.post(endpoint, json=payload)
                    if res.status_code == 429 or res.status_code >= 500:
                        # transient server-side condition: retry/failover
                        raise httpx.HTTPStatusError(
                            f"HTTP {res.status_code}", request=res.request, response=res
                        )
                    res.raise_for_status()  # other 4xx: config problem, no retry
                    body = res.json()
                    if "error" in body:
                        # A protocol error is an ANSWER (e.g. unhealthy node,
                        # unknown account) — retrying cannot change it.
                        raise SolanaRpcError(
                            f"{method}: {body['error'].get('message', 'rpc error')}",
                            details=body["error"],
                        )
                    return body.get("result")
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.2 * (2**attempt))
            logger.warning("RPC endpoint %s exhausted for %s — failing over", endpoint, method)

        raise SolanaRpcError(f"{method} failed on all endpoints", details=str(last_exc))

    # --- typed methods ----------------------------------------------------

    async def get_health(self) -> bool:
        """True when the node reports itself healthy."""
        return await self.call("getHealth") == "ok"

    async def get_slot(self) -> int:
        """Current slot height."""
        return int(await self.call("getSlot"))

    async def get_epoch_info(self) -> EpochInfo:
        """Current epoch and position within it."""
        r = await self.call("getEpochInfo")
        return EpochInfo(
            epoch=r["epoch"],
            slot_index=r["slotIndex"],
            slots_in_epoch=r["slotsInEpoch"],
            absolute_slot=r["absoluteSlot"],
        )

    async def get_recent_tps(self, samples: int = 5) -> float | None:
        """Average transactions/second over the most recent samples."""
        perf = await self.call("getRecentPerformanceSamples", [samples])
        if not perf:
            return None
        tx = sum(s["numTransactions"] for s in perf)
        secs = sum(s["samplePeriodSecs"] for s in perf)
        return round(tx / secs, 1) if secs else None

    async def get_token_supply(self, mint: str) -> TokenSupply:
        """Total supply of an SPL token."""
        v = (await self.call("getTokenSupply", [mint]))["value"]
        return TokenSupply(amount=v["amount"], decimals=v["decimals"], ui_amount=v["uiAmount"])

    async def get_token_largest_accounts(self, mint: str) -> list[dict[str, Any]]:
        """Top-20 largest holder accounts (LPs included) for concentration checks."""
        return (await self.call("getTokenLargestAccounts", [mint]))["value"]

    async def get_token_authorities(self, mint: str) -> TokenAuthorities:
        """Mint/freeze authority state — the primary on-chain rug signal."""
        info = await self.call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        parsed = (((info or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info")
        if not parsed:
            raise SolanaRpcError(f"mint {mint} is not a parseable SPL token account")
        return TokenAuthorities(
            mint_authority=parsed.get("mintAuthority"),
            freeze_authority=parsed.get("freezeAuthority"),
        )

    async def get_balance_lamports(self, pubkey: str) -> int:
        """SOL balance of an address, in lamports (read-only)."""
        r = await self.call("getBalance", [pubkey])
        return int((r or {}).get("value", 0))

    async def get_token_balance_raw(self, owner: str, mint: str) -> tuple[int, int]:
        """(raw_amount, decimals) an owner holds of one SPL mint, summed
        across their token accounts. (0, 0) when they hold none."""
        r = await self.call(
            "getTokenAccountsByOwner",
            [owner, {"mint": mint}, {"encoding": "jsonParsed"}],
        )
        accounts = (r or {}).get("value") or []
        total = 0
        decimals = 0
        for acct in accounts:
            info = acct["account"]["data"]["parsed"]["info"]["tokenAmount"]
            total += int(info["amount"])
            decimals = int(info["decimals"])
        return total, decimals

    async def get_chain_status(self) -> ChainStatus:
        """Aggregate snapshot; individual probe failures degrade, never raise."""

        async def safe(coro: Any) -> Any:
            try:
                return await coro
            except Exception:  # noqa: BLE001 — status must always assemble
                return None

        health, slot, epoch, tps = await asyncio.gather(
            safe(self.get_health()),
            safe(self.get_slot()),
            safe(self.get_epoch_info()),
            safe(self.get_recent_tps()),
        )
        return ChainStatus(healthy=bool(health), slot=slot, epoch=epoch, tps=tps)


# --- process-wide singleton (same lifecycle pattern as database.engine) ---

_client: RpcClient | None = None


def get_rpc_client(settings: Settings) -> RpcClient:
    """Return the shared RpcClient, creating it on first use.

    The endpoint order implements failover: configured endpoint first
    (Helius when a key is set), public mainnet RPC as the fallback.
    """
    global _client
    if _client is None:
        endpoints = [settings.rpc_url]
        if settings.rpc_url != PUBLIC_RPC:
            endpoints.append(PUBLIC_RPC)
        _client = RpcClient(endpoints)
        logger.info("Solana RPC client created (%d endpoint(s))", len(endpoints))
    return _client


async def close_rpc_client() -> None:
    """Dispose the shared client. Called from the app lifespan shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Solana RPC client closed")
