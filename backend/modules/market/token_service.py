"""Token service — metadata accessor for agent consumers.

Narrow surface for the Research and Risk Agents: identity, supply, and
authority state (the rug signal), without exposing the whole module.
"""

from models.schemas.solana import TokenAuthorities
from modules.market.market_manager import MarketManager
from modules.market.market_models import TokenInfo


class TokenService:
    """Token identity + on-chain metadata view."""

    def __init__(self, manager: MarketManager) -> None:
        self._manager = manager

    async def info(self, mint: str) -> TokenInfo:
        """Full token info: market view + decimals/supply/authorities."""
        return await self._manager.get_token_info(mint)

    async def authorities(self, mint: str) -> TokenAuthorities | None:
        """Mint/freeze authority state only (Risk Agent fast path)."""
        return (await self._manager.get_token_info(mint)).authorities
