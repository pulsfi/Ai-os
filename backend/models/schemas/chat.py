"""Chat API contracts."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One turn of the conversation."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32_000)


class ChatRequest(BaseModel):
    """POST /chat body — the conversation so far, oldest first."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=100)


class ChatStatus(BaseModel):
    """GET /chat/status — is the assistant available?"""

    configured: bool
    model: str
