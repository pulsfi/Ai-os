"""Solana RPC adapter — on-chain token metadata (not prices).

Delegates to modules.solana.RpcClient (the single RPC path) and exposes
metadata the market view needs: decimals, supply, authorities.
"""

import logging

from models.schemas.solana import TokenAuthorities
from modules.solana import RpcClient

logger = logging.getLogger(__name__)


class SolanaRpcAdapter:
    """On-chain metadata source; read-only by construction."""

    name = "solana_rpc"

    def __init__(self, rpc: RpcClient) -> None:
        self._rpc = rpc

    async def token_metadata(
        self, mint: str
    ) -> tuple[int | None, float | None, TokenAuthorities | None]:
        """Return (decimals, ui_supply, authorities); Nones on failure.

        Failures are logged and degraded, never raised — metadata is
        enrichment, not a hard dependency of the market view.
        """
        decimals: int | None = None
        supply: float | None = None
        authorities: TokenAuthorities | None = None
        try:
            s = await self._rpc.get_token_supply(mint)
            decimals, supply = s.decimals, s.ui_amount
        except Exception as exc:  # noqa: BLE001
            logger.warning("supply lookup failed for %s: %s", mint[:8], exc)
        try:
            authorities = await self._rpc.get_token_authorities(mint)
        except Exception as exc:  # noqa: BLE001
            logger.warning("authority lookup failed for %s: %s", mint[:8], exc)
        return decimals, supply, authorities
