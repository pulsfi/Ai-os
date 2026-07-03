"""Time helpers — one canonical way to get 'now' across the codebase.

Always timezone-aware UTC. Naive datetimes are banned by convention
(they are the root of every 'why is the chart shifted 5 hours' bug).
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def iso_utc() -> str:
    """Current UTC time as a compact ISO-8601 string (second precision)."""
    return utc_now().isoformat(timespec="seconds")
