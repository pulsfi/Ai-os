"""Application settings — the single source of configuration truth.

Loads from (in priority order): process environment > .env file > defaults.
Every field is typed and validated by Pydantic at startup, so a bad value
fails the boot loudly instead of surfacing mid-request.

Usage (always through DI, never instantiate directly in modules):

    from config import get_settings
    settings = get_settings()
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment; drives logging and safety behavior."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """All runtime configuration for the backend.

    Field names map 1:1 to environment variables (case-insensitive),
    documented in `.env.example`.
    """

    # --- application ---
    app_name: str = "os-ai-backend"
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True

    # --- logging ---
    log_level: str = "INFO"
    log_json: bool = False  # True => structured JSON logs (production)

    # --- api ---
    api_v1_prefix: str = "/api/v1"
    # Browser origins allowed to call this API (the Next.js frontend).
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]

    # --- infrastructure ---
    database_url: str = "postgresql+asyncpg://osai:osai@localhost:5432/osai"
    database_echo: bool = False  # echo SQL statements (debugging only)
    redis_url: str = "redis://localhost:6379/0"

    # --- solana (read-only data access; no wallets, no transactions) ---
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    helius_api_key: str = ""

    # --- AI chat (Claude API; key-gated like the market providers) ---
    anthropic_api_key: str = ""  # empty = chat endpoint reports "not configured"
    anthropic_model: str = "claude-opus-4-8"
    chat_max_tokens: int = 4096

    # --- vault bridge for the agents API (read-only) ---
    agents_dir: str = "04 Agents"  # relative to vault_path

    # --- market intelligence (READ-ONLY market data) ---
    birdeye_api_key: str = ""  # optional 5th provider; empty = skipped
    market_cache_ttl_seconds: int = 30  # Redis/mem cache expiry per token
    market_refresh_enabled: bool = False  # background scheduler on/off
    market_refresh_seconds: int = 300  # scheduler interval
    market_provider_min_interval_seconds: float = 1.0  # per-provider rate guard
    # Tracked token mints (SOL, JUP, BONK, WIF by default). Env: JSON list.
    market_watchlist: list[str] = [
        "So11111111111111111111111111111111111111112",
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    ]

    # --- obsidian vault bridge (the knowledge layer) ---
    vault_path: Path = Path("..")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # unknown env vars are not our concern
    )

    @property
    def rpc_url(self) -> str:
        """Effective Solana RPC endpoint.

        A Helius key, when present, upgrades the default public endpoint —
        mirrors the convention used by the Node automation layer.
        """
        if self.helius_api_key and "helius" not in self.solana_rpc_url:
            return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
        return self.solana_rpc_url

    @property
    def is_production(self) -> bool:
        """True when running with production safety expectations."""
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    `lru_cache` gives one parse per process while staying trivially
    overridable in tests (`get_settings.cache_clear()`).
    """
    return Settings()
