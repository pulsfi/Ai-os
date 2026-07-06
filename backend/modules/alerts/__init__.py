"""Alerts module — in-app feed + optional Telegram delivery.

Every important event (kill switch, mode change, real trade, daily report)
emits an Alert. Alerts always land in an in-process ring buffer (so the
UI works with zero config) and, when TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
are set, are also pushed to Telegram. Key-gated like the other providers.
"""

from modules.alerts.service import AlertService, close_alerts, get_alert_service

__all__ = ["AlertService", "close_alerts", "get_alert_service"]
