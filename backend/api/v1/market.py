"""Market Intelligence endpoints — read-only market data.

Thin routers per the architecture: all logic lives in modules/market.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.dependencies import HeliusDep, MarketManagerDep, PumpFunDep, SolanaClientDep
from core.exceptions import AppError
from modules.bots.scoring import score_launch, score_pumpfun_launch
from modules.market.helius import TokenActivity
from modules.market.market_models import (
    HistoryPoint,
    MarketStatus,
    TokenInfo,
    TokenMarketData,
)
from modules.market.pumpfun import PumpCoin

router = APIRouter()


@router.get("/activity/{mint}", response_model=TokenActivity)
async def token_activity(
    mint: str, helius: HeliusDep, limit: int = Query(default=50, ge=10, le=100)
) -> TokenActivity:
    """Live flow for a token from Helius parsed transactions: buys vs
    sells, unique wallets, tx rate. Key-gated (HELIUS_API_KEY)."""
    return await helius.get_token_activity(mint, limit)


class ScoreFactor(BaseModel):
    name: str
    points: float
    max_points: float
    detail: str


class TokenScore(BaseModel):
    """The AI Decision Card verdict — same engine the sniper uses."""

    mint: str
    score: float
    approved: bool
    factors: list[ScoreFactor]
    rejects: list[str]
    # Raw sub-signals surfaced for the card's individual meters.
    buy_ratio_pct: float | None = None
    unique_wallets: int | None = None
    liquidity_usd: float | None = None
    market_cap: float | None = None
    mint_revoked: bool | None = None
    freeze_revoked: bool | None = None


@router.get("/score/{mint}", response_model=TokenScore)
async def token_score(
    mint: str,
    rpc: SolanaClientDep,
    helius: HeliusDep,
    manager: MarketManagerDep,
    pumpfun: PumpFunDep,
) -> TokenScore:
    """Score any token 0-100 on measurable signals (the confidence engine
    behind the AI Decision Card). Unmeasurable signals count as unknown —
    never fabricated.

    A token still on the pump.fun bonding curve is scored on pump.fun-native
    signals (market cap, bonding progress, community, authorities), because
    Helius / DEX aggregators are blind to it until it graduates. Everything
    else uses on-chain flow + authorities. This is a single-snapshot view,
    so market-cap velocity (the live sniper's confirmation gate) is shown as
    unknown rather than blocking the card."""
    # On-chain mint/freeze authority — a rug/honeypot gate for both paths.
    mint_revoked = freeze_revoked = None
    try:
        auth = await rpc.get_token_authorities(mint)
        mint_revoked = auth.mint_authority is None
        freeze_revoked = auth.freeze_authority is None
    except AppError:
        pass

    # Bonding-curve token? Score it the way the sniper now does.
    coin = None
    try:
        coin = await pumpfun.get_coin(mint)
    except AppError:
        pass
    if coin is not None and not coin.complete:
        age_s = (datetime.now(timezone.utc) - coin.created_at).total_seconds()
        verdict = score_pumpfun_launch(
            mcap_usd=coin.usd_market_cap,
            mcap_growth_pct_per_min=None,  # single snapshot has no velocity
            bonding_progress_pct=coin.bonding_progress_pct,
            reply_count=coin.reply_count,
            age_s=age_s,
            mint_revoked=mint_revoked,
            freeze_revoked=freeze_revoked,
            min_mcap_usd=5_000, max_mcap_usd=60_000, max_age_s=300,
            require_growth_confirmation=False,
        )
        return TokenScore(
            mint=mint, score=verdict.score, approved=verdict.approved,
            factors=[ScoreFactor(**f.__dict__) for f in verdict.factors],
            rejects=verdict.rejects,
            market_cap=coin.usd_market_cap,
            mint_revoked=mint_revoked, freeze_revoked=freeze_revoked,
        )

    # Graduated / non-pump token: on-chain flow + market context.
    buy_ratio = wallets = swaps = None
    if helius.is_configured:
        try:
            act = await helius.get_token_activity(mint, limit=40)
            buy_ratio, wallets, swaps = act.buy_ratio_pct, act.unique_wallets, act.swaps
        except AppError:
            pass

    mcap = liq = None
    try:
        info = await manager.get_token_info(mint)
        mcap = info.market.market_cap
        liq = info.market.liquidity_usd
    except AppError:
        pass

    verdict = score_launch(
        mcap_usd=mcap, age_s=None,
        mint_revoked=mint_revoked, freeze_revoked=freeze_revoked,
        buy_ratio_pct=buy_ratio, unique_wallets=wallets, swaps=swaps,
        min_mcap_usd=0, max_mcap_usd=10**12, max_age_s=10**9,
    )
    return TokenScore(
        mint=mint, score=verdict.score, approved=verdict.approved,
        factors=[ScoreFactor(**f.__dict__) for f in verdict.factors],
        rejects=verdict.rejects,
        buy_ratio_pct=buy_ratio, unique_wallets=wallets, liquidity_usd=liq,
        market_cap=mcap, mint_revoked=mint_revoked, freeze_revoked=freeze_revoked,
    )


@router.get("/pumpfun/new", response_model=list[PumpCoin])
async def pumpfun_new(
    pumpfun: PumpFunDep, limit: int = Query(default=20, ge=1, le=50)
) -> list[PumpCoin]:
    """Freshest pump.fun launches, newest first (read-only discovery)."""
    return await pumpfun.get_new_coins(limit)


@router.get("/pumpfun/graduating", response_model=list[PumpCoin])
async def pumpfun_graduating(
    pumpfun: PumpFunDep, limit: int = Query(default=20, ge=1, le=50)
) -> list[PumpCoin]:
    """Highest-cap coins still on the bonding curve — closest to graduation."""
    return await pumpfun.get_graduating(limit)


@router.get("/pumpfun/coin/{mint}", response_model=PumpCoin)
async def pumpfun_coin(mint: str, pumpfun: PumpFunDep) -> PumpCoin:
    """One pump.fun launch by mint address."""
    return await pumpfun.get_coin(mint)


@router.get("/tokens", response_model=list[TokenMarketData])
async def tokens(manager: MarketManagerDep) -> list[TokenMarketData]:
    """Merged multi-provider data for every tracked token."""
    return await manager.get_watchlist()


@router.get("/trending", response_model=list[TokenMarketData])
async def trending(manager: MarketManagerDep) -> list[TokenMarketData]:
    """Tracked tokens ranked by 24h change, top movers first."""
    return await manager.get_trending()


@router.get("/status", response_model=MarketStatus)
async def status(manager: MarketManagerDep) -> MarketStatus:
    """Module health: providers, cache, scheduler, refresh timestamps."""
    return manager.status()


@router.get("/token/{address}", response_model=TokenInfo)
async def token(address: str, manager: MarketManagerDep) -> TokenInfo:
    """One token: merged market data + on-chain metadata (authorities)."""
    return await manager.get_token_info(address)


@router.get("/history/{address}", response_model=list[HistoryPoint])
async def history(
    address: str,
    manager: MarketManagerDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[HistoryPoint]:
    """Stored snapshots for one token, newest first (requires PostgreSQL)."""
    return await manager.get_history(address, limit)
