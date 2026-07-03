"""Create all database tables from the ORM metadata.

Usage (PostgreSQL must be running, e.g. `docker compose up -d db`):

    python -m scripts.init_db

TODO(migrations): replace with Alembic once the schema stabilizes;
create_all is acceptable only for the foundation phase.
"""

import asyncio
import logging

import models.orm  # noqa: F401 — imports register all tables on Base.metadata
from config import get_settings
from core.logging import setup_logging
from database.base import Base
from database.engine import dispose_engine, get_engine

logger = logging.getLogger(__name__)


async def main() -> None:
    """Connect, create tables, report, disconnect."""
    settings = get_settings()
    setup_logging(settings)
    engine = get_engine(settings)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created: %s", ", ".join(Base.metadata.tables))
    except Exception as exc:  # noqa: BLE001 — operator-facing script
        logger.error("Could not initialize database: %s", exc)
        logger.error("Is PostgreSQL running? Try: docker compose up -d db")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
