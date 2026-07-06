"""Alert contracts."""

from typing import Literal

from pydantic import BaseModel


class Alert(BaseModel):
    """One system alert (also mirrored to Telegram when configured)."""

    level: Literal["info", "warning", "critical"]
    title: str
    message: str
    ts: str


class AlertsStatus(BaseModel):
    """Alert feed + delivery config (never exposes the token)."""

    telegram_configured: bool
    alerts: list[Alert]
