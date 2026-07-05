"""Bot strategies — pure decision logic over live market data.

Each strategy answers two questions and nothing else:
  1. find_entries(): which tokens to (paper-)buy right now?
  2. current_price(): what is a held token worth right now?

Exits (take-profit / stop-loss / max-hold) are uniform policy and live in
the runner, not here. Strategies never touch the ledger and never sign
anything — they see data, they return signals.

Pump.fun price note: launches have a fixed 1B token supply, so
price ≈ usd_market_cap / 1e9. PnL on those positions therefore tracks
market-cap change — recorded honestly in each trade's entry_note.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from core.exceptions import AppError
from modules.market import MarketManager
from modules.market.pumpfun import PumpCoin, PumpFunClient

logger = logging.getLogger(__name__)

_PUMP_SUPPLY = 1_000_000_000  # fixed pump.fun launch supply


@dataclass(frozen=True)
class EntrySignal:
    """A strategy's decision to open one paper position."""

    mint: str
    symbol: str
    price_usd: float
    note: str


def _pump_price(coin: PumpCoin) -> float | None:
    if coin.usd_market_cap is None or coin.usd_market_cap <= 0:
        return None
    return coin.usd_market_cap / _PUMP_SUPPLY


class Strategy(ABC):
    """Decision logic; stateless between ticks except what data provides."""

    name: str

    def __init__(self, pumpfun: PumpFunClient, market: MarketManager) -> None:
        self._pumpfun = pumpfun
        self._market = market

    @abstractmethod
    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        """Up to `slots` new entry signals, excluding already-held mints."""

    async def current_price(self, mint: str) -> float | None:
        """Live price for a held mint; None = data unavailable this tick."""
        try:
            coin = await self._pumpfun.get_coin(mint)
        except AppError:
            return None
        return _pump_price(coin)


class NewLaunchSniper(Strategy):
    """Buys brand-new pump.fun launches that show immediate traction.

    Filter: younger than max_age_s, market cap already above the floor
    (someone besides the creator bought), at least one reply. Meme-coin
    sniping is the highest-risk style there is — which is exactly why it
    runs on virtual dollars while the track record accumulates.
    """

    name = "new_launch_sniper"

    def __init__(
        self,
        pumpfun: PumpFunClient,
        market: MarketManager,
        max_age_s: float = 180.0,
        min_mcap_usd: float = 6_000.0,
        max_mcap_usd: float = 60_000.0,
    ) -> None:
        super().__init__(pumpfun, market)
        self._max_age_s = max_age_s
        self._min_mcap = min_mcap_usd
        self._max_mcap = max_mcap_usd

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        coins = await self._pumpfun.get_new_coins(limit=30)
        now = datetime.now(timezone.utc)
        signals: list[EntrySignal] = []
        for coin in coins:
            if len(signals) >= slots:
                break
            price = _pump_price(coin)
            if (
                coin.mint in held_mints
                or coin.complete
                or price is None
                or coin.usd_market_cap is None
                or not (self._min_mcap <= coin.usd_market_cap <= self._max_mcap)
                or (now - coin.created_at).total_seconds() > self._max_age_s
                or coin.reply_count < 1
            ):
                continue
            signals.append(
                EntrySignal(
                    mint=coin.mint,
                    symbol=coin.symbol or coin.mint[:6],
                    price_usd=price,
                    note=(
                        f"new launch {int((now - coin.created_at).total_seconds())}s old, "
                        f"mcap ${coin.usd_market_cap:,.0f}, {coin.reply_count} replies "
                        f"(price=mcap/1B)"
                    ),
                )
            )
        return signals


class GraduationMomentum(Strategy):
    """Buys coins close to graduating off the pump.fun bonding curve.

    Graduation (Raydium listing) is the classic momentum event. Entry is
    a BAND, not a floor: the first live track record (2026-07-04, 0/3,
    -$2.43) showed that entries at 99.9-100% progress are too late — the
    pump is already priced in. 85-98.5% rides the final push instead of
    buying its top. Skips already-complete coins.
    """

    name = "graduation_momentum"

    def __init__(
        self,
        pumpfun: PumpFunClient,
        market: MarketManager,
        min_progress_pct: float = 85.0,
        max_progress_pct: float = 98.5,
    ) -> None:
        super().__init__(pumpfun, market)
        self._min_progress = min_progress_pct
        self._max_progress = max_progress_pct

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        coins = await self._pumpfun.get_graduating(limit=30)
        signals: list[EntrySignal] = []
        for coin in coins:
            if len(signals) >= slots:
                break
            price = _pump_price(coin)
            if (
                coin.mint in held_mints
                or coin.complete
                or price is None
                or not (self._min_progress <= coin.bonding_progress_pct <= self._max_progress)
            ):
                continue
            signals.append(
                EntrySignal(
                    mint=coin.mint,
                    symbol=coin.symbol or coin.mint[:6],
                    price_usd=price,
                    note=(
                        f"graduation {coin.bonding_progress_pct}% complete, "
                        f"mcap ${(coin.usd_market_cap or 0):,.0f} (price=mcap/1B)"
                    ),
                )
            )
        return signals


class TrendScalper(Strategy):
    """Scalps the tracked watchlist's strongest 24h movers.

    Uses the merged multi-provider price (real price, not an mcap proxy),
    so this bot doubles as the sanity baseline for the other two.
    """

    name = "trend_scalper"

    def __init__(
        self,
        pumpfun: PumpFunClient,
        market: MarketManager,
        min_change_24h_pct: float = 3.0,
    ) -> None:
        super().__init__(pumpfun, market)
        self._min_change = min_change_24h_pct

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        tokens = await self._market.get_trending()
        signals: list[EntrySignal] = []
        for t in tokens:
            if len(signals) >= slots:
                break
            if (
                t.mint in held_mints
                or t.price_usd is None
                or t.change_24h is None
                or t.change_24h < self._min_change
            ):
                continue
            signals.append(
                EntrySignal(
                    mint=t.mint,
                    symbol=t.symbol or t.mint[:6],
                    price_usd=t.price_usd,
                    note=f"trending +{t.change_24h:.2f}%/24h across {len(t.sources)} providers",
                )
            )
        return signals

    async def current_price(self, mint: str) -> float | None:
        try:
            tokens = await self._market.get_watchlist()
        except AppError:
            return None
        for t in tokens:
            if t.mint == mint:
                return t.price_usd
        return None
