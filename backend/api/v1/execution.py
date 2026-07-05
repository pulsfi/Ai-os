"""Execution endpoints (Stage 5) — status, readiness, kill switch, dry-run.

There is deliberately NO endpoint that arms live trading or sends a real
order. Arming is env-only (EXECUTION_ARMED), and even then the executor
is dry-run. The kill switch can only HALT execution, never start it.
"""

from fastapi import APIRouter

from core.dependencies import (
    BotManagerDep,
    ExecutorDep,
    RiskEngineDep,
    SettingsDep,
    SolanaClientDep,
    SwapBuilderDep,
)
from models.schemas.execution import (
    BuildBuyRequest,
    BuildSellRequest,
    BuiltSwap,
    ExecutionMode,
    ExecutionStatus,
    GoLiveReadiness,
    OrderRequest,
    OrderResult,
    WalletBalance,
)
from modules.execution import evaluate_readiness

router = APIRouter()


@router.get("/status", response_model=ExecutionStatus)
async def execution_status(risk: RiskEngineDep, settings: SettingsDep) -> ExecutionStatus:
    """Current execution state — armed?, mode, limits, kill switch, day PnL."""
    armed = risk.armed and not risk.kill_switch
    return ExecutionStatus(
        armed=risk.armed,
        mode=ExecutionMode(settings.execution_mode)
        if settings.execution_mode in (m.value for m in ExecutionMode)
        else ExecutionMode.DRY_RUN,
        kill_switch=risk.kill_switch,
        live_available=False,  # the live path is an intentional stub
        limits=risk.limits,
        realized_pnl_today_usd=risk.realized_today,
        reason=(
            "Kill switch engaged — execution halted."
            if risk.kill_switch
            else "Disarmed — paper/dry-run only. Set EXECUTION_ARMED to enable dry-run gating."
            if not risk.armed
            else "Armed for DRY-RUN only. No live path exists; nothing real is sent."
        ),
    )


@router.get("/readiness", response_model=GoLiveReadiness)
async def go_live_readiness(bots: BotManagerDep, settings: SettingsDep) -> GoLiveReadiness:
    """Scorecard: does the paper record justify real money yet?"""
    fleet = next((p for p in bots.performance() if p.bot_id == "fleet"), None)
    return evaluate_readiness(fleet, bots.first_entry_ts(), settings)


@router.post("/kill/{state}", response_model=ExecutionStatus)
async def set_kill_switch(
    state: str, risk: RiskEngineDep, settings: SettingsDep
) -> ExecutionStatus:
    """Engage ('on') or release ('off') the global halt. Safe either way —
    it can only stop execution, never begin it."""
    risk.set_kill_switch(state == "on")
    return await execution_status(risk, settings)


@router.post("/dry-run", response_model=OrderResult)
async def dry_run_order(order: OrderRequest, executor: ExecutorDep) -> OrderResult:
    """Route an intended order through the risk engine + a REAL Jupiter
    quote, and record a simulated fill. Signs nothing, sends nothing."""
    return await executor.execute(order)


# --- manual (Phantom-signed) real trades ---------------------------------------
# The backend BUILDS unsigned transactions; only the user's wallet can sign,
# one explicit approval per trade. No private key ever reaches the server.


@router.get("/wallet/{pubkey}/balance", response_model=WalletBalance)
async def wallet_balance(pubkey: str, rpc: SolanaClientDep) -> WalletBalance:
    """Read-only SOL balance of a PUBLIC address (never a key)."""
    lamports = await rpc.get_balance_lamports(pubkey)
    return WalletBalance(address=pubkey, sol=round(lamports / 1e9, 6), lamports=lamports)


@router.post("/trade/build-buy", response_model=BuiltSwap)
async def build_buy(body: BuildBuyRequest, swaps: SwapBuilderDep) -> BuiltSwap:
    """Build an UNSIGNED SOL→token buy for the user's wallet to approve."""
    return await swaps.build_buy(body.user_pubkey, body.mint, body.usd_size)


@router.post("/trade/build-sell", response_model=BuiltSwap)
async def build_sell(body: BuildSellRequest, swaps: SwapBuilderDep) -> BuiltSwap:
    """Build an UNSIGNED token→SOL sell (full balance) for the user to approve."""
    return await swaps.build_sell(body.user_pubkey, body.mint)
