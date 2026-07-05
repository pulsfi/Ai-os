"""Vault module — read-only bridge to the Obsidian vault's markdown notes.

The vault (repo root) is the knowledge layer. This module is the ONLY
backend code allowed to touch vault files, so path safety (allowlist +
containment) is enforced in exactly one place.

Public surface:
    VaultService, get_vault_service

TODO(vault): VaultWriter — write/update notes preserving frontmatter,
             append to agent report logs (needed for Stage 6 automation).
TODO(vault): wikilink integrity checker (port of the ad-hoc link audit).
"""

from modules.vault.vault_service import VaultService, get_vault_service

__all__ = ["VaultService", "get_vault_service"]
