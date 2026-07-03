"""Vault module — bridge between the platform and the Obsidian vault.

The vault (repo root) is the knowledge layer: agents read their missions
from it and write their reports back to it. This module is the ONLY code
allowed to touch vault files, so note conventions (frontmatter, wikilinks)
are enforced in exactly one place.

TODO(vault): VaultReader — list notes, read note, parse frontmatter.
TODO(vault): VaultWriter — write/update notes preserving frontmatter,
             append to agent report logs.
TODO(vault): wikilink integrity checker (port of the ad-hoc link audit).
TODO(vault): expose read-only notes API at /api/v1/vault.
"""
