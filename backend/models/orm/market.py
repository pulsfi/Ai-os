"""Market persistence entities.

These mirror the proven SQLite schema in `09 Automation/market/market.db`
(the Node automation layer) and are its PostgreSQL migration target.

TODO(migration): write a one-shot importer SQLite -> PostgreSQL (scripts/).
TODO(migration): add Alembic and generate the initial revision from these.
"""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Token(Base):
    """One tracked token — normalized identity, referenced by snapshots.

    Keeping identity separate from observations avoids duplicating
    symbol/decimals on every snapshot row (the normalization requirement).
    """

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    mint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(128))
    decimals: Mapped[int | None] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column()


class MarketSnapshot(Base):
    """One multi-source market observation of one token at one moment.

    (token_id, ts) is unique — the same instant is never stored twice,
    which is how the 'avoid duplicate data' requirement is enforced at
    the schema level rather than by application discipline.
    """

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("tokens.id"), index=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    mint: Mapped[str | None] = mapped_column(String(64))
    price_usd: Mapped[float | None] = mapped_column(Float)
    change_24h: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)
    liquidity: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    fdv: Mapped[float | None] = mapped_column(Float)
    sources: Mapped[str | None] = mapped_column(String(128))  # e.g. "coingecko+dexscreener"

    __table_args__ = (
        Index("ix_market_snapshots_symbol_ts", "symbol", "ts"),
        UniqueConstraint("token_id", "ts", name="uq_snapshot_token_ts"),
    )


class PaperTrade(Base):
    """A hypothetical trade recorded at real prices (Stage 3 discipline).

    NOTE: paper only — this entity carries no wallet, key, or transaction
    fields by design. Live execution is out of scope for the foundation.
    """

    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    mint: Mapped[str | None] = mapped_column(String(64))
    usd_size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_ts: Mapped[datetime] = mapped_column(index=True)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_ts: Mapped[datetime | None] = mapped_column()
    pnl_usd: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    reasoning: Mapped[str | None] = mapped_column(Text)
    exit_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed
