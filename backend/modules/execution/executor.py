"""Executors — DRY_RUN (implemented) and LIVE (guarded stub).

DryRunExecutor fetches a REAL Jupiter quote for the intended swap so the
whole routing path is exercised, then records a SIMULATED fill. It never
builds, signs, or sends a transaction, and never reads a private key.

The live path is a deliberate stub: constructing/signing real transactions
is the part that must not be written under time pressure or before the
paper record justifies it. `LiveExecutor` raises a clear error explaining
exactly what building it responsibly requires.
"""

import logging

import httpx

from config import Settings
from core.exceptions import AppError, ExternalServiceError
from models.schemas.execution import ExecutionMode, OrderRequest, OrderResult
from modules.execution.risk_engine import RiskEngine

logger = logging.getLogger(__name__)

# Jupiter public quote API (read-only; returns route + price impact).
_JUPITER_QUOTE = "https://lite-api.jup.ag/swap/v1/quote"
_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
_SOL_MINT = "So11111111111111111111111111111111111111112"


class LiveExecutionUnavailable(AppError):
    """Real-money execution is intentionally not implemented yet."""

    status_code = 501
    code = "live_execution_unavailable"


class DryRunExecutor:
    """Simulates execution end-to-end: real quote in, logged fill out."""

    mode = ExecutionMode.DRY_RUN

    def __init__(self, risk: RiskEngine, http: httpx.AsyncClient | None = None) -> None:
        self._risk = risk
        self._http = http or httpx.AsyncClient(timeout=15.0)

    async def _quote(self, order: OrderRequest) -> dict | None:
        """Real Jupiter quote for $usd_size of USDC into the token (buy) or
        back out (sell). Returns None if the route can't be fetched — the
        dry run still records the intended order honestly."""
        # 6-decimal USDC; approximate the USD notional as USDC in-amount.
        amount = int(order.usd_size * 1_000_000)
        input_mint = _USDC_MINT if order.side == "buy" else order.mint
        output_mint = order.mint if order.side == "buy" else _USDC_MINT
        try:
            res = await self._http.get(
                _JUPITER_QUOTE,
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": amount,
                    "slippageBps": self._risk.limits.max_slippage_bps,
                },
            )
            if res.status_code != 200:
                return None
            return res.json()
        except httpx.HTTPError:
            return None

    async def execute(self, order: OrderRequest) -> OrderResult:
        """Risk-check, fetch a real quote, record a simulated fill."""
        decision = self._risk.check_order(order.usd_size, order.side)
        if not decision.allowed:
            return OrderResult(
                accepted=False,
                mode=self.mode,
                mint=order.mint,
                symbol=order.symbol,
                side=order.side,
                usd_size=order.usd_size,
                detail=f"DRY-RUN blocked by risk engine: {decision.reason}",
            )
        quote = await self._quote(order)
        out_amount: str | None = None
        impact: float | None = None
        fill: float | None = None
        if quote is not None:
            out_amount = str(quote.get("outAmount")) if quote.get("outAmount") else None
            raw_impact = quote.get("priceImpactPct")
            try:
                impact = round(float(raw_impact) * 100, 4) if raw_impact is not None else None
            except (TypeError, ValueError):
                impact = None
            if order.side == "buy" and out_amount:
                # tokens received per USD spent -> implied USD price/token
                try:
                    fill = order.usd_size / (int(out_amount) / 1e9) / 1e9 if int(out_amount) else None
                except (ValueError, ZeroDivisionError):
                    fill = None
        logger.info(
            "DRY-RUN %s %s $%.2f — quote=%s impact=%s (no tx signed)",
            order.side, order.symbol, order.usd_size, out_amount, impact,
        )
        return OrderResult(
            accepted=True,
            mode=self.mode,
            mint=order.mint,
            symbol=order.symbol,
            side=order.side,
            usd_size=order.usd_size,
            simulated_fill_price=fill,
            quote_out_amount=out_amount,
            price_impact_pct=impact,
            detail=(
                "DRY-RUN: real Jupiter route fetched, fill simulated. "
                "No transaction was built, signed, or sent."
                if quote is not None
                else "DRY-RUN: quote unavailable; intended order recorded, nothing sent."
            ),
        )

    async def aclose(self) -> None:
        await self._http.aclose()


class LiveExecutor:
    """Placeholder for real-money execution — intentionally inert.

    Building this responsibly requires, in order: (1) a green go-live
    readiness scorecard, (2) a wallet/keypair loaded from a secure store
    (never the repo), (3) transaction build + sign + send with priority
    fees and slippage protection, (4) confirmation + reconciliation, and
    (5) a small-size ramp. None of that is done here on purpose.
    """

    mode = ExecutionMode.LIVE

    async def execute(self, order: OrderRequest) -> OrderResult:  # noqa: ARG002
        raise LiveExecutionUnavailable(
            "Live execution is not implemented. The system trades in dry-run "
            "only until the go-live readiness scorecard is green and a wallet "
            "is deliberately configured. This gate is intentional."
        )


_executor: DryRunExecutor | None = None


def get_executor(settings: Settings, risk: RiskEngine) -> DryRunExecutor:
    """Only the dry-run executor is ever returned. Even with EXECUTION_MODE
    set to 'live', we refuse to hand back a live executor because the live
    path is not implemented — safety over configuration."""
    global _executor
    if _executor is None:
        _executor = DryRunExecutor(risk)
    if settings.execution_mode == ExecutionMode.LIVE.value:
        logger.warning(
            "EXECUTION_MODE=live requested but live execution is unavailable; "
            "using dry-run executor (no real orders)."
        )
    return _executor


async def close_executor() -> None:
    global _executor
    if _executor is not None:
        await _executor.aclose()
        _executor = None
