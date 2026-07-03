"""Apply SQL migrations in order, tracking them in schema_migrations.

Usage (PostgreSQL must be running):

    python -m scripts.migrate

Simple by design: numbered .sql files in database/migrations/, applied
once each, recorded by filename. Alembic replaces this when the schema
starts evolving (docs/ROADMAP.md Phase 1).
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import text

from config import get_settings
from core.logging import setup_logging
from database.engine import dispose_engine, get_engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "database" / "migrations"


async def main() -> None:
    """Apply every pending migration inside one transaction each."""
    settings = get_settings()
    setup_logging(settings)
    engine = get_engine(settings)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations "
                    "(filename TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT now())"
                )
            )
            applied = {
                r[0] for r in (await conn.execute(text("SELECT filename FROM schema_migrations")))
            }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                logger.info("skip  %s (already applied)", path.name)
                continue
            async with engine.begin() as conn:
                await conn.execute(text(path.read_text(encoding="utf-8")))
                await conn.execute(
                    text("INSERT INTO schema_migrations (filename) VALUES (:f)"),
                    {"f": path.name},
                )
            logger.info("apply %s", path.name)
        logger.info("Migrations complete")
    except Exception as exc:  # noqa: BLE001 — operator-facing script
        logger.error("Migration failed: %s", exc)
        logger.error("Is PostgreSQL running? Try: docker compose up -d db")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
