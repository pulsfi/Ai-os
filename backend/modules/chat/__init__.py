"""AI Chat module — Claude-powered assistant, key-gated like the market providers.

Public surface:
    ChatService       — streaming chat completion against the Claude API
    get_chat_service  — process-wide singleton accessor
"""

from modules.chat.chat_service import (
    ChatService,
    close_chat_service,
    get_chat_service,
)

__all__ = ["ChatService", "close_chat_service", "get_chat_service"]
