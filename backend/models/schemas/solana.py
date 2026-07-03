"""Typed contracts for Solana chain data."""

from pydantic import BaseModel, Field, computed_field


class EpochInfo(BaseModel):
    """Current epoch position of the chain."""

    epoch: int
    slot_index: int = Field(description="Slots elapsed inside this epoch")
    slots_in_epoch: int
    absolute_slot: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_pct(self) -> float:
        """How far through the epoch we are, 0-100."""
        if self.slots_in_epoch <= 0:
            return 0.0
        return round(self.slot_index / self.slots_in_epoch * 100, 1)


class ChainStatus(BaseModel):
    """Aggregate chain snapshot returned by GET /solana/status."""

    healthy: bool = Field(description="RPC getHealth == ok")
    slot: int | None
    epoch: EpochInfo | None
    tps: float | None = Field(default=None, description="Recent average transactions/second")


class TokenSupply(BaseModel):
    """SPL token supply, straight from getTokenSupply."""

    amount: str = Field(description="Raw amount in base units (string: may exceed 2^53)")
    decimals: int
    ui_amount: float | None


class TokenAuthorities(BaseModel):
    """Mint/freeze authority state — the core rug-check signal."""

    mint_authority: str | None = Field(description="None = revoked (safe)")
    freeze_authority: str | None = Field(description="None = revoked (safe)")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_fully_revoked(self) -> bool:
        """True when neither authority exists — supply and transfers are immutable."""
        return self.mint_authority is None and self.freeze_authority is None
