"""Liquidity service — depth accessor for agent consumers.

The Risk Agent's primary feed: liquidity depth and where it sits (DEX,
pairs) decide whether a position could ever be exited.
"""

from modules.market.market_manager import MarketManager
from modules.market.market_models import TradingPair


class LiquidityService:
    """Liquidity-focused view of the market data."""

    def __init__(self, manager: MarketManager) -> None:
        self._manager = manager

    async def liquidity_usd(self, mint: str) -> float | None:
        """Deepest-pool liquidity in USD."""
        return (await self._manager.get_token(mint)).liquidity_usd

    async def pairs(self, mint: str) -> list[TradingPair]:
        """Trading pairs (major quotes only) with per-pair liquidity."""
        return (await self._manager.get_token(mint)).pairs

    async def is_thin(self, mint: str, threshold_usd: float = 50_000) -> bool:
        """Risk Agent helper: True when liquidity is below the threshold."""
        liq = await self.liquidity_usd(mint)
        return liq is None or liq < threshold_usd
