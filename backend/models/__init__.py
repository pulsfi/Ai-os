"""Models package.

- `models.orm`     — SQLAlchemy entities (persistence layer)
- `models.schemas` — Pydantic models (API contracts / validation)

Kept strictly separate: the API contract must be able to evolve without a
database migration, and vice versa.
"""
