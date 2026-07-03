"""Declarative base for all ORM entities.

The naming convention makes every constraint/index name deterministic —
mandatory for clean migrations once Alembic lands (see docs/ROADMAP.md).
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of every ORM entity in `models/`."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
