"""Read-only vault notes bridge.

Serves markdown notes from inside the Obsidian vault to the frontend.
Strictly read-only and strictly contained: every requested path is
resolved and must land inside the vault root — traversal (`..`, absolute
paths, drive letters) gets a 404, never a file. Only `.md` files are
visible; everything else in the vault does not exist to this API.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from core.exceptions import NotFoundError
from models.schemas.vault import VaultNote, VaultNoteContent

logger = logging.getLogger(__name__)

# Vault folders exposed to the API. Deliberately an allowlist: the vault
# also holds automation configs and .env files that must stay invisible.
_ALLOWED_DIRS = (
    "10 Memory",
    "12 Daily Notes",
    "00 Dashboard",
)


class VaultService:
    """Lists and reads markdown notes from allowlisted vault folders."""

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.vault_path).resolve()

    def _safe_dir(self, rel_dir: str) -> Path:
        if rel_dir not in _ALLOWED_DIRS:
            raise NotFoundError(f"Vault folder not exposed: {rel_dir}")
        path = (self._root / rel_dir).resolve()
        if not path.is_dir() or self._root not in path.parents:
            raise NotFoundError(f"Vault folder not found: {rel_dir}")
        return path

    def allowed_dirs(self) -> list[str]:
        """The folders a client may browse (drives the Memory page tabs)."""
        return [d for d in _ALLOWED_DIRS if (self._root / d).is_dir()]

    def list_notes(self, rel_dir: str) -> list[VaultNote]:
        """Markdown notes in one allowlisted folder, newest-modified first."""
        directory = self._safe_dir(rel_dir)
        notes: list[VaultNote] = []
        for f in directory.glob("*.md"):
            stat = f.stat()
            notes.append(
                VaultNote(
                    name=f.stem,
                    path=f"{rel_dir}/{f.name}",
                    modified=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(timespec="seconds"),
                    size_bytes=stat.st_size,
                )
            )
        notes.sort(key=lambda n: n.modified, reverse=True)
        return notes

    def read_note(self, rel_path: str) -> VaultNoteContent:
        """One note's markdown. The path must be `<allowed dir>/<file>.md`."""
        rel = Path(rel_path)
        # Exactly one directory level, from the allowlist, .md only.
        if (
            len(rel.parts) != 2
            or rel.parts[0] not in _ALLOWED_DIRS
            or rel.suffix.lower() != ".md"
        ):
            raise NotFoundError(f"Note not found: {rel_path}")
        file = (self._root / rel).resolve()
        if self._root not in file.parents or not file.is_file():
            raise NotFoundError(f"Note not found: {rel_path}")
        try:
            content = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise NotFoundError(f"Note not readable: {rel_path}") from exc
        return VaultNoteContent(
            name=file.stem,
            path=rel_path,
            content=content,
            modified=datetime.fromtimestamp(
                file.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds"),
        )


_service: VaultService | None = None


def get_vault_service(settings: Settings) -> VaultService:
    """Process-wide singleton, same pattern as the other modules."""
    global _service
    if _service is None:
        _service = VaultService(settings)
    return _service
