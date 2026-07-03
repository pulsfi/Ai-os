"""Volume service — activity accessor for agent consumers.

Feeds the Monitoring Agent (volume anomalies) and the Research Agent
(activity summaries) without exposing the full module surface.
"""

from modules.market.market_manager import MarketManager


class VolumeService:
    """Volume/market-cap view of the market data."""

    def __init__(self, manager: MarketManager) -> None:
        self._manager = manager

    async def volume_24h(self, mint: str) -> float | None:
        """24h traded volume in USD."""
        return (await self._manager.get_token(mint)).volume_24h

    async def market_cap(self, mint: str) -> float | None:
        """Market capitalization (falls back to FDV upstream when absent)."""
        return (await self._manager.get_token(mint)).market_cap

    async def fdv(self, mint: str) -> float | None:
        """Fully diluted valuation."""
        return (await self._manager.get_token(mint)).fdv
