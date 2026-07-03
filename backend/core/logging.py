"""Centralized logging configuration.

One `setup_logging()` call at boot configures the root logger; every module
then simply does `logger = logging.getLogger(__name__)`. Two output modes:

- console (development): human-readable single line
- JSON (production, LOG_JSON=true): machine-parseable structured records

Deliberately stdlib-only at the foundation layer — no logging framework
lock-in before we know the observability stack.
"""

import json
import logging
import logging.config
from datetime import datetime, timezone

from config import Settings


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(settings: Settings) -> None:
    """Configure the root logger. Idempotent — safe to call more than once."""
    handler: dict[str, object] = {
        "class": "logging.StreamHandler",
        "formatter": "json" if settings.log_json else "console",
    }
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "datefmt": "%H:%M:%S",
                },
                "json": {"()": JsonFormatter},
            },
            "handlers": {"default": handler},
            "root": {"level": settings.log_level.upper(), "handlers": ["default"]},
            "loggers": {
                # uvicorn's own loggers should flow through our handler
                "uvicorn": {"level": settings.log_level.upper()},
                "uvicorn.access": {"level": "WARNING"},  # health probes are noisy
            },
        }
    )
