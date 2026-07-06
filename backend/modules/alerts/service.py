"""AlertService — buffer alerts in-process, optionally push to Telegram.

emit() is synchronous and safe to call from anywhere (including sync
code like the risk engine): it stores the alert and, if a Telegram bot is
configured and an event loop is running, schedules the send in the
background. A failed Telegram send never affects the caller.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone

import httpx

from config import Settings
from models.schemas.alerts import Alert

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}


class AlertService:
    """Ring buffer of recent alerts + optional Telegram forwarding."""

    def __init__(self, settings: Settings) -> None:
        self._token = settings.telegram_bot_token.strip()
        self._chat = settings.telegram_chat_id.strip()
        self._buffer: deque[Alert] = deque(maxlen=100)
        self._http: httpx.AsyncClient | None = None

    @property
    def telegram_configured(self) -> bool:
        return bool(self._token and self._chat)

    def emit(self, level: str, title: str, message: str) -> Alert:
        """Record an alert; forward to Telegram when configured."""
        alert = Alert(level=level, title=title, message=message, ts=_now())  # type: ignore[arg-type]
        self._buffer.appendleft(alert)
        logger.info("ALERT [%s] %s — %s", level, title, message)
        if self.telegram_configured:
            try:
                asyncio.get_running_loop().create_task(self._send(alert))
            except RuntimeError:
                pass  # no running loop (e.g. a sync unit test): buffer only
        return alert

    async def _send(self, alert: Alert) -> None:
        try:
            if self._http is None:
                self._http = httpx.AsyncClient(timeout=10.0)
            text = f"{_EMOJI.get(alert.level, '')} <b>{alert.title}</b>\n{alert.message}"
            await self._http.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": self._chat, "text": text, "parse_mode": "HTML"},
            )
        except Exception as exc:  # noqa: BLE001 — delivery is best-effort
            logger.warning("telegram alert send failed: %s", exc)

    def recent(self, limit: int = 50) -> list[Alert]:
        return list(self._buffer)[:limit]

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None


_service: AlertService | None = None


def get_alert_service(settings: Settings) -> AlertService:
    """Process-wide singleton, same pattern as the other modules."""
    global _service
    if _service is None:
        _service = AlertService(settings)
    return _service


async def close_alerts() -> None:
    global _service
    if _service is not None:
        await _service.aclose()
        _service = None
