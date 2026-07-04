"""Chat endpoints — Claude-powered assistant with SSE streaming.

POST /chat streams the reply as Server-Sent Events:

    data: {"type": "delta", "text": "..."}
    data: {"type": "done"}
    data: {"type": "error", "message": "..."}   (only on mid-stream failure)

Configuration errors (no API key) are raised BEFORE streaming starts, so
they arrive as the standard JSON error envelope with a proper status code.
"""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.dependencies import ChatServiceDep
from core.exceptions import AppError
from models.schemas.chat import ChatRequest, ChatStatus

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(payload: dict) -> str:
    """Encode one SSE data frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/status", response_model=ChatStatus)
async def chat_status(chat: ChatServiceDep) -> ChatStatus:
    """Whether chat is configured (never exposes the key itself)."""
    return ChatStatus(configured=chat.is_configured, model=chat.model_name)


@router.post("")
async def send_message(body: ChatRequest, chat: ChatServiceDep) -> StreamingResponse:
    """Stream the assistant's reply for the given conversation."""
    # Fail fast (as a normal JSON error) before the stream is committed.
    chat.ensure_configured()

    messages = [m.model_dump() for m in body.messages]

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for delta in chat.stream_reply(messages):
                yield _sse({"type": "delta", "text": delta})
            yield _sse({"type": "done"})
        except AppError as exc:
            # Headers are already sent — deliver the error inside the stream.
            logger.warning("chat stream failed: %s", exc.message)
            yield _sse({"type": "error", "message": exc.message})
        except Exception:
            logger.exception("unexpected chat stream failure")
            yield _sse({"type": "error", "message": "Chat stream failed unexpectedly."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )
