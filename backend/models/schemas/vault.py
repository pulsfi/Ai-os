"""Vault notes API contracts (read-only)."""

from pydantic import BaseModel


class VaultNote(BaseModel):
    """Listing entry for one markdown note."""

    name: str
    path: str  # "<allowed dir>/<file>.md" — the id used by /vault/note
    modified: str
    size_bytes: int


class VaultNoteContent(BaseModel):
    """One note with its full markdown body."""

    name: str
    path: str
    content: str
    modified: str
