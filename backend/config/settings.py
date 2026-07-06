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

    # --- alerts (Telegram; empty = in-app feed only) ---
    telegram_bot_token: str = ""  # from @BotFather
    telegram_chat_id: str = ""  # your chat/channel id

    # --- AI chat (Claude API; key-gated like the market providers) ---
    anthropic_api_key: str = ""  # empty = chat endpoint reports "not configured"
    anthropic_model: str = "claude-opus-4-8"
    chat_max_tokens: int = 4096

    # --- vault bridge for the agents API (read-only) ---
    agents_dir: str = "04 Agents"  # relative to vault_path

    # --- agent runtime (Stage 6: the 7-agent pipeline runs live) ---
    agents_runtime_enabled: bool = True  # build + autostart the pipeline loop
    agents_cycle_seconds: float = 60.0  # one full pipeline pass per this many s

    # --- paper trading ledger (read-only; written by the Node scalper) ---
    paper_db_path: str = "09 Automation/market/market.db"  # relative to vault_path

    # --- bot fleet (PAPER MODE ONLY — virtual USD, no wallets, no keys) ---
    bots_enabled: bool = True  # build the fleet + expose /bots
    bots_autostart: bool = False  # start every bot loop at app boot
    bots_interval_seconds: float = 20.0  # tick cadence per bot
    bots_sniper_interval_seconds: float = 5.0  # sniper's faster fallback cadence
    # Real-time pump.fun launch stream (PumpPortal WS); false = REST-only
    pumpportal_enabled: bool = True
    bots_usd_per_trade: float = 50.0  # virtual position size
    bots_db_path: str = "data/paper_bots.db"  # bot ledger, relative to backend/
    # Honest paper pricing: model that exits aren't free and can't be dumped
    # at an overshot mark on illiquid meme coins. Every close takes a
    # slippage haircut, and per-trade gains are capped to a realizable level.
    bots_exit_slippage_bps: int = 200  # 2% haircut on every simulated exit
    bots_max_gain_pct: float = 100.0  # cap credited gain per trade (anti-moonshot)

    # --- daily fleet report (auto vault write; same constrained path) ---
    daily_report_enabled: bool = False  # true = write the diary automatically
    daily_report_hour_utc: int = 20  # when to write, 0-23 UTC

    # --- execution layer (Stage 5) — SHIPS DISARMED, NO KEYS, NO SIGNING ---
    # Master switch. Even when true, only the dry-run executor exists — the
    # live path is a deliberate stub. Real money never trades from config alone.
    execution_armed: bool = False
    execution_mode: str = "dry_run"  # dry_run (only implemented) | live (stubbed)
    exec_max_position_usd: float = 10.0  # hard per-order cap (start tiny)
    exec_daily_loss_limit_usd: float = 25.0  # halt trading after this daily loss
    exec_max_concurrent_positions: int = 2
    exec_max_slippage_bps: int = 150  # 1.5% max slippage on quotes
    # Manual (Phantom-signed) trades: the user approves each one, so this is
    # just a fat-finger guard on buy size. Raise it if you want bigger trades.
    manual_trade_max_usd: float = 100.0
    # Exposure guard: cap total real USD bought via the wallet per UTC day.
    manual_daily_buy_limit_usd: float = 500.0
    live_trades_db_path: str = "data/live_trades.db"  # real-trade record, rel. backend/
    # Go-live readiness gates (all must pass before live is justifiable).
    golive_min_closed_trades: int = 50
    golive_min_win_rate_pct: float = 55.0
    golive_min_realized_pnl_usd: float = 25.0
    golive_min_days: float = 7.0
    # Sanity gate: an average paper trade above this is implausible for real
    # fills and signals the record can't be trusted (blocks a premature go-live).
    golive_max_avg_trade_pct: float = 30.0

    # --- market intelligence (READ-ONLY market data) ---
    birdeye_api_key: str = ""  # optional 5th provider; empty = skipped
    # Birdeye's free tier throttles harder than the others (429s); give it
    # a longer per-call gap so it contributes reliably instead of erroring.
    birdeye_min_interval_seconds: float = 2.5
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
