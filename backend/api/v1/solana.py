"""Solana endpoints — read-only chain data."""

from fastapi import APIRouter

from core.dependencies import SolanaClientDep
from models.schemas.solana import ChainStatus, TokenAuthorities

router = APIRouter()


@router.get("/status", response_model=ChainStatus)
async def chain_status(rpc: SolanaClientDep) -> ChainStatus:
    """Live chain snapshot: health, slot, epoch progress, recent TPS."""
    return await rpc.get_chain_status()


@router.get("/token/{mint}/authorities", response_model=TokenAuthorities)
async def token_authorities(mint: str, rpc: SolanaClientDep) -> TokenAuthorities:
    """Mint/freeze authority state for an SPL token (the on-chain rug check)."""
    return await rpc.get_token_authorities(mint)
