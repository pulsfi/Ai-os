"""WebSocket endpoint — live push of the bot fleet + latest trades.

One socket per client; every `interval` seconds the server pushes:

    {"type": "fleet", "ts": "...", "bots": [BotStatus...], "trades": [BotTrade...]}

This replaces frontend polling for the fleet view. Read-only by design:
inbound messages are ignored — controls stay on the authenticated-origin
REST endpoints, so a WS client can watch but never act.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from modules.bots import get_bot_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_PUSH_INTERVAL_S = 3.0


@router.websocket("")
async def fleet_stream(websocket: WebSocket) -> None:
    """Push a fleet snapshot every few seconds until the client leaves."""
    await websocket.accept()
    settings = websocket.app.state.settings
    manager = get_bot_manager(settings)
    logger.info("ws client connected (%s)", websocket.client)
    try:
        while True:
            payload = {
                "type": "fleet",
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bots": [s.model_dump(mode="json") for s in manager.statuses()],
                "trades": [
                    t.model_dump(mode="json") for t in manager.trades(None, 20)
                ],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(_PUSH_INTERVAL_S)
    except WebSocketDisconnect:
        logger.info("ws client disconnected (%s)", websocket.client)
