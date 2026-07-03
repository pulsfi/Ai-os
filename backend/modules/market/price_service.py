"""Price service — focused price accessor for agent consumers.

Thin facade over the manager (Interface Segregation): the Strategy and
Learning Agents that only care about price depend on this narrow surface,
not on the whole market module.
"""

from modules.market.market_manager import MarketManager


class PriceService:
    """Price-only view of the market data."""

    def __init__(self, manager: MarketManager) -> None:
        self._manager = manager

    async def current_price(self, mint: str) -> float | None:
        """Latest merged USD price for a token (cache-first)."""
        return (await self._manager.get_token(mint)).price_usd

    async def price_change_24h(self, mint: str) -> float | None:
        """24h price change percentage."""
        return (await self._manager.get_token(mint)).change_24h
