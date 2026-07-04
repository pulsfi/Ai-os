"""Claude-backed chat service.

Design mirrors the market providers: the capability is key-gated —
without ANTHROPIC_API_KEY the service reports "not configured" through
the standard error envelope instead of pretending to work.

Streaming contract (consumed by api/v1/chat.py as SSE):
    yields text deltas as they arrive from the Claude API.
"""

import logging
from collections.abc import AsyncIterator

from anthropic import APIStatusError, AsyncAnthropic

from config import Settings
from core.exceptions import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)

# The assistant knows what it is part of; grounded, no invented data.
SYSTEM_PROMPT = (
    "You are the AI assistant inside 'OS AI' — a personal AI operating system "
    "for Solana research and market intelligence built on an Obsidian vault, "
    "a FastAPI backend, and a 7-agent pipeline (Research, Strategy, Risk, "
    "Execution, Monitoring, Learning, Documentation). "
    "Be concise and practical. When asked about live prices or on-chain "
    "state, remind the user the Dashboard/Trading pages show live data; "
    "never invent numbers. Trading is paper-mode only until the roadmap's "
    "Stage 5 gate opens — never suggest otherwise."
)


class ChatService:
    """Streams chat completions from the Claude API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncAnthropic | None = None

    @property
    def is_configured(self) -> bool:
        """True when an API key is present (mirrors provider gating)."""
        return bool(self._settings.anthropic_api_key)

    @property
    def model_name(self) -> str:
        """The Claude model this service talks to."""
        return self._settings.anthropic_model

    def ensure_configured(self) -> None:
        """Raise the standard configuration error when no key is set."""
        if not self.is_configured:
            raise ConfigurationError(
                "Chat is not configured: set ANTHROPIC_API_KEY in backend/.env",
                details={"setting": "ANTHROPIC_API_KEY"},
            )

    def _require_client(self) -> AsyncAnthropic:
        self.ensure_configured()
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    async def stream_reply(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Yield the assistant's reply as text deltas.

        `messages` is the prior conversation, oldest first:
        [{"role": "user"|"assistant", "content": "..."}]
        """
        client = self._require_client()
        try:
            async with client.messages.stream(
                model=self._settings.anthropic_model,
                max_tokens=self._settings.chat_max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,  # type: ignore[arg-type]
                thinking={"type": "adaptive"},
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except APIStatusError as exc:
            logger.warning("Claude API error %s: %s", exc.status_code, exc.message)
            raise ExternalServiceError(
                f"Claude API error ({exc.status_code})",
                details={"status": exc.status_code},
            ) from exc

    async def aclose(self) -> None:
        """Release the underlying HTTP client (called at app shutdown)."""
        if self._client is not None:
            await self._client.close()
            self._client = None


_service: ChatService | None = None


def get_chat_service(settings: Settings) -> ChatService:
    """Process-wide singleton, same pattern as get_market_manager."""
    global _service
    if _service is None:
        _service = ChatService(settings)
    return _service


async def close_chat_service() -> None:
    """Release the singleton's HTTP client (app shutdown)."""
    global _service
    if _service is not None:
        await _service.aclose()
        _service = None
