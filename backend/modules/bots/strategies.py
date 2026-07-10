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
from modules.bots.scoring import ConfidenceScore, score_launch
from modules.market import MarketManager
from modules.market.helius import HeliusClient
from modules.market.pumpfun import PumpCoin, PumpFunClient
from modules.market.pumpportal import LaunchStream
from modules.solana import RpcClient

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

    async def on_position_closed(self, mint: str) -> None:
        """Hook: the runner closed a position in this mint (default no-op)."""


class NewLaunchSniper(Strategy):
    """Buys brand-new pump.fun launches that show immediate traction.

    Two-stage filter, like a pro sniper:
      1. Launch shape — younger than max_age_s, market cap above the floor
         (someone besides the creator bought), at least one reply.
      2. FLOW CONFIRMATION (when Helius is configured) — the token's live
         transactions must show real buying: enough swaps, enough distinct
         wallets, and buys outweighing sells. A pump with no flow behind
         it is a trap; those candidates are skipped, and a failed flow
         lookup skips the coin too (conservative by default).

    Meme-coin sniping is the highest-risk style there is — which is
    exactly why it runs on virtual dollars while the record accumulates.
    """

    name = "new_launch_sniper"

    def __init__(
        self,
        pumpfun: PumpFunClient,
        market: MarketManager,
        helius: HeliusClient | None = None,
        stream: LaunchStream | None = None,
        rpc: RpcClient | None = None,
        max_age_s: float = 300.0,
        min_mcap_usd: float = 5_000.0,
        max_mcap_usd: float = 60_000.0,
        # Confidence gate: score every candidate 0-100 on measurable
        # on-chain + flow signals; enter only at/above this. Missing demand
        # data can't reach it, so the bot stays out rather than guessing.
        min_confidence: float = 55.0,
    ) -> None:
        super().__init__(pumpfun, market)
        self._helius = helius
        self._stream = stream
        self._rpc = rpc
        self._max_age_s = max_age_s
        self._min_mcap = min_mcap_usd
        self._max_mcap = max_mcap_usd
        self._min_confidence = min_confidence

    async def _sol_usd(self) -> float | None:
        """SOL/USD from the cached watchlist (30s TTL) for mcapSol -> USD."""
        try:
            tokens = await self._market.get_watchlist()
        except AppError:
            return None
        for t in tokens:
            if (t.symbol or "").upper() == "SOL":
                return t.price_usd
        return None

    async def _confidence(self, mint: str, mcap_usd: float | None, age_s: float | None) -> ConfidenceScore:
        """Gather measurable signals and score the launch 0-100.

        On-chain authority state (RPC) + demand flow (Helius) + market
        context. Anything that can't be fetched counts as unknown (0
        points) — never fabricated. The verdict is fully explainable and
        gets written into the trade note.
        """
        # Demand flow (buys vs sells, wallets, swaps).
        buy_ratio = wallets = swaps = None
        if self._helius is not None and self._helius.is_configured:
            try:
                act = await self._helius.get_token_activity(mint, limit=30)
                buy_ratio, wallets, swaps = act.buy_ratio_pct, act.unique_wallets, act.swaps
            except AppError:
                pass  # unknown flow -> scored as 0, won't reach threshold

        # On-chain mint/freeze authority (rug / honeypot gates).
        mint_revoked = freeze_revoked = None
        if self._rpc is not None:
            try:
                auth = await self._rpc.get_token_authorities(mint)
                mint_revoked = auth.mint_authority is None
                freeze_revoked = auth.freeze_authority is None
            except AppError:
                pass  # unknown authority -> 0 points (not a hard reject)

        return score_launch(
            mcap_usd=mcap_usd,
            age_s=age_s,
            mint_revoked=mint_revoked,
            freeze_revoked=freeze_revoked,
            buy_ratio_pct=buy_ratio,
            unique_wallets=wallets,
            swaps=swaps,
            min_mcap_usd=self._min_mcap,
            max_mcap_usd=self._max_mcap,
            max_age_s=self._max_age_s,
            min_confidence=self._min_confidence,
        )

    async def _stream_candidates(
        self, held_mints: set[str], slots: int
    ) -> list[EntrySignal]:
        """Fast path: launches pushed by the live stream (no REST latency).

        The stream carries no reply counts, so the flow gate is the
        traction check here — real buys or no entry.
        """
        if self._stream is None:
            return []
        events = self._stream.recent(self._max_age_s)
        if not events:
            return []
        sol_usd = await self._sol_usd()
        if sol_usd is None:
            return []
        import time as _time

        signals: list[EntrySignal] = []
        for event in events:
            if len(signals) >= slots:
                break
            if event.mint in held_mints or event.mcap_sol is None:
                continue
            mcap_usd = event.mcap_sol * sol_usd
            if not (self._min_mcap <= mcap_usd <= self._max_mcap):
                continue
            age_s = _time.monotonic() - event.received_at
            verdict = await self._confidence(event.mint, mcap_usd, age_s)
            if not verdict.approved:
                continue  # scored too low / hard-rejected -> skip this launch
            signals.append(
                EntrySignal(
                    mint=event.mint,
                    symbol=event.symbol or event.mint[:6],
                    price_usd=mcap_usd / _PUMP_SUPPLY,
                    note=(
                        f"stream-detected {int(age_s)}s ago, mcap ${mcap_usd:,.0f}, "
                        f"{verdict.note()} (price=mcap/1B)"
                    ),
                )
            )
        return signals

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        # 1) Stream first — the whole point of fast sniping.
        signals = await self._stream_candidates(held_mints, slots)
        taken = {s.mint for s in signals} | held_mints

        # 2) REST sweep fills remaining slots (also covers stream downtime).
        if len(signals) < slots:
            coins = await self._pumpfun.get_new_coins(limit=30)
            now = datetime.now(timezone.utc)
            for coin in coins:
                if len(signals) >= slots:
                    break
                price = _pump_price(coin)
                if (
                    coin.mint in taken
                    or coin.complete
                    or price is None
                    or coin.usd_market_cap is None
                    or not (self._min_mcap <= coin.usd_market_cap <= self._max_mcap)
                    or (now - coin.created_at).total_seconds() > self._max_age_s
                    or coin.reply_count < 1
                ):
                    continue
                age_s = (now - coin.created_at).total_seconds()
                verdict = await self._confidence(coin.mint, coin.usd_market_cap, age_s)
                if not verdict.approved:
                    continue  # scored too low / hard-rejected
                signals.append(
                    EntrySignal(
                        mint=coin.mint,
                        symbol=coin.symbol or coin.mint[:6],
                        price_usd=price,
                        note=(
                            f"new launch {int(age_s)}s old, "
                            f"mcap ${coin.usd_market_cap:,.0f}, {coin.reply_count} replies, "
                            f"{verdict.note()} (price=mcap/1B)"
                        ),
                    )
                )

        # Live trade marks for everything we're about to hold.
        if self._stream is not None:
            for s in signals:
                await self._stream.watch(s.mint)
        return signals

    async def current_price(self, mint: str) -> float | None:
        """Streamed trade mark first (sub-second fresh), REST fallback."""
        if self._stream is not None:
            mcap_sol = self._stream.latest_mcap_sol(mint)
            if mcap_sol is not None:
                sol_usd = await self._sol_usd()
                if sol_usd is not None:
                    return mcap_sol * sol_usd / _PUMP_SUPPLY
        return await super().current_price(mint)

    async def on_position_closed(self, mint: str) -> None:
        if self._stream is not None:
            await self._stream.unwatch(mint)


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


class FlowScalper(Strategy):
    """Disciplined scalper: only buys liquid watchlist tokens that show
    CONFIRMED real buy-pressure right now (Helius flow), rather than chasing
    24h charts or lottery-ticket launches.

    Why this is structurally lower-loss than the sniper:
      * liquid tokens → real fills, ~0 slippage (25 bps), no mcap proxy;
      * enters only when live flow shows more buyers than sellers across
        several wallets → riding demand, not hoping for it;
      * small quick targets with a tight stop → many small wins, capped
        downside. (Still: only the paper record proves it profits.)
    """

    name = "flow_scalper"

    def __init__(
        self,
        pumpfun: PumpFunClient,
        market: MarketManager,
        helius: HeliusClient | None = None,
        min_buy_ratio_pct: float = 58.0,
        min_wallets: int = 5,
        min_swaps: int = 6,
    ) -> None:
        super().__init__(pumpfun, market)
        self._helius = helius
        self._min_buy_ratio = min_buy_ratio_pct
        self._min_wallets = min_wallets
        self._min_swaps = min_swaps

    async def find_entries(self, held_mints: set[str], slots: int) -> list[EntrySignal]:
        tokens = await self._market.get_watchlist()
        signals: list[EntrySignal] = []
        for t in tokens:
            if len(signals) >= slots:
                break
            # Not up on the day? skip — scalp with the short-term tide, not against it.
            if (
                t.mint in held_mints
                or t.price_usd is None
                or t.change_24h is None
                or t.change_24h < 0
            ):
                continue
            flow = await self._flow(t.mint)
            if flow is None:
                continue  # no confirmed buying right now
            signals.append(
                EntrySignal(
                    mint=t.mint,
                    symbol=t.symbol or t.mint[:6],
                    price_usd=t.price_usd,
                    note=f"flow-scalp {flow}",
                )
            )
        return signals

    async def _flow(self, mint: str) -> str | None:
        """Confirmed buy-pressure note, or None to skip."""
        if self._helius is None or not self._helius.is_configured:
            # No key: fall back to letting it trade (basic uptrend filter
            # already applied), stated honestly.
            return "flow gate off (no HELIUS_API_KEY)"
        try:
            act = await self._helius.get_token_activity(mint, limit=40)
        except AppError:
            return None
        if (
            act.swaps < self._min_swaps
            or act.unique_wallets < self._min_wallets
            or act.buy_ratio_pct is None
            or act.buy_ratio_pct < self._min_buy_ratio
        ):
            return None
        return f"{act.buy_ratio_pct}% buys, {act.unique_wallets} wallets"

    async def current_price(self, mint: str) -> float | None:
        try:
            tokens = await self._market.get_watchlist()
        except AppError:
            return None
        for t in tokens:
            if t.mint == mint:
                return t.price_usd
        return None
