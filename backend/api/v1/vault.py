"""Vault endpoints — read-only markdown notes from allowlisted folders."""

from fastapi import APIRouter, Query

from core.dependencies import VaultServiceDep
from models.schemas.vault import VaultNote, VaultNoteContent

router = APIRouter()


@router.get("/dirs", response_model=list[str])
async def allowed_dirs(vault: VaultServiceDep) -> list[str]:
    """Folders exposed to the UI (allowlist ∩ actually present)."""
    return vault.allowed_dirs()


@router.get("/notes", response_model=list[VaultNote])
async def list_notes(
    vault: VaultServiceDep,
    dir: str = Query(default="10 Memory", max_length=100),
) -> list[VaultNote]:
    """Markdown notes in one allowlisted folder, newest-modified first."""
    return vault.list_notes(dir)


@router.get("/note", response_model=VaultNoteContent)
async def read_note(
    vault: VaultServiceDep,
    path: str = Query(max_length=300),
) -> VaultNoteContent:
    """One note's full markdown (404 outside the allowlist — always)."""
    return vault.read_note(path)
