"""Vault endpoints — read-only notes, plus ONE constrained write:
the Documentation Agent's daily bot report."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.dependencies import BotManagerDep, VaultServiceDep
from models.schemas.vault import VaultNote, VaultNoteContent
from modules.vault.daily_report import build_daily_report

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


class DailyReportResult(BaseModel):
    """Where the report landed."""

    path: str
    written: bool = True


@router.post("/daily-report", response_model=DailyReportResult)
async def write_daily_report(
    vault: VaultServiceDep, bots: BotManagerDep
) -> DailyReportResult:
    """Append the fleet's performance to TODAY's daily note.

    The only write the vault API has: target path is computed from the
    date server-side, so nothing the client sends reaches the filesystem.
    """
    section = build_daily_report(bots.statuses(), bots.performance())
    return DailyReportResult(path=vault.append_daily_report(section))
