"""Market repository — the only code that touches market tables.

Persistence is enrichment for this module: if PostgreSQL is down, live
reads still work (providers + cache); only history is unavailable. Every
write is logged per the module's logging requirements.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.orm.market import MarketSnapshot, Token
from modules.market.market_models import HistoryPoint, TokenMarketData
from utils.time import utc_now

logger = logging.getLogger(__name__)


class MarketRepository:
    """CRUD for tokens and snapshots over an injected session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_token(self, mint: str, symbol: str | None, decimals: int | None) -> Token:
        """Return the Token row for a mint, creating it on first sight."""
        token = (
            await self._session.execute(select(Token).where(Token.mint == mint))
        ).scalar_one_or_none()
        if token is None:
            token = Token(mint=mint, symbol=symbol, decimals=decimals, first_seen=utc_now())
            self._session.add(token)
            await self._session.flush()
            logger.info("db write: new token %s (%s)", symbol or "?", mint[:8])
        elif symbol and token.symbol != symbol:
            token.symbol = symbol  # symbols can be learned later than the mint
        return token

    async def insert_snapshot(self, data: TokenMarketData, decimals: int | None = None) -> None:
        """Store one merged observation; (token_id, ts) unique => no dupes."""
        token = await self.upsert_token(data.mint, data.symbol, decimals)
        self._session.add(
            MarketSnapshot(
                token_id=token.id,
                ts=data.fetched_at.replace(tzinfo=None),  # naive UTC in DB
                symbol=data.symbol or "?",
                mint=data.mint,
                price_usd=data.price_usd,
                change_24h=data.change_24h,
                volume_24h=data.volume_24h,
                liquidity=data.liquidity_usd,
                market_cap=data.market_cap,
                fdv=data.fdv,
                sources="+".join(data.sources),
            )
        )
        await self._session.commit()
        logger.info("db write: snapshot %s @ %s", data.symbol or data.mint[:8], data.price_usd)

    async def history(self, mint: str, limit: int = 100) -> list[HistoryPoint]:
        """Most recent stored snapshots for one token, newest first."""
        rows = (
            await self._session.execute(
                select(MarketSnapshot)
                .where(MarketSnapshot.mint == mint)
                .order_by(MarketSnapshot.ts.desc())
                .limit(limit)
            )
        ).scalars()
        return [
            HistoryPoint(
                ts=r.ts,
                price_usd=r.price_usd,
                change_24h=r.change_24h,
                volume_24h=r.volume_24h,
                liquidity_usd=r.liquidity,
                market_cap=r.market_cap,
                fdv=r.fdv,
                sources=r.sources,
            )
            for r in rows
        ]
