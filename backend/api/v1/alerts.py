"""Alerts endpoints — the recent feed + a test emitter."""

from fastapi import APIRouter, Query

from core.dependencies import AlertsDep
from models.schemas.alerts import Alert, AlertsStatus

router = APIRouter()


@router.get("", response_model=AlertsStatus)
async def list_alerts(
    alerts: AlertsDep, limit: int = Query(default=50, ge=1, le=100)
) -> AlertsStatus:
    """Recent alerts + whether Telegram delivery is configured."""
    return AlertsStatus(
        telegram_configured=alerts.telegram_configured,
        alerts=alerts.recent(limit),
    )


@router.post("/test", response_model=Alert)
async def test_alert(alerts: AlertsDep) -> Alert:
    """Emit a test alert (verifies Telegram delivery when configured)."""
    return alerts.emit(
        "info", "Test alert", "Alerts are working. Telegram fires too if configured."
    )
