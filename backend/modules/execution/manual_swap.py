"""Manual swap builder — real trades, non-custodial via the user's wallet.

This is the safe way to trade real money: the backend BUILDS a Jupiter
swap transaction for the user's PUBLIC key and hands it back UNSIGNED.
Only the user's wallet (Phantom) can sign it, and the user approves every
single trade with an explicit click. The backend never holds a private
key and physically cannot move the user's funds on its own.

Guard rails that still apply to a manual trade:
  * global kill switch halts building (a real "stop everything")
  * a per-trade USD cap on buys prevents fat-finger mistakes
Autonomous bots never reach this path — they have no key to sign with,
which is precisely why they stay paper until the go-live gate opens.
"""

import base64
import logging

import httpx

from config import Settings
from core.exceptions import AppError, ExternalServiceError
from models.schemas.execution import BuiltSwap
from modules.execution.risk_engine import RiskEngine
from modules.market import MarketManager
from modules.solana import RpcClient

logger = logging.getLogger(__name__)

# Jupiter's current free-tier host (quote-api.jup.ag/v6 was retired).
_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"
_SWAP_URL = "https://lite-api.jup.ag/swap/v1/swap"
_SOL_MINT = "So11111111111111111111111111111111111111112"


class ManualTradeBlocked(AppError):
    """A guard rail (kill switch / cap) refused to build the trade."""

    status_code = 409
    code = "manual_trade_blocked"


class ManualSwapBuilder:
    """Builds unsigned Jupiter swaps for a user-approved (Phantom) flow."""

    def __init__(
        self,
        risk: RiskEngine,
        rpc: RpcClient,
        market: MarketManager,
        settings: Settings,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._risk = risk
        self._rpc = rpc
        self._market = market
        self._settings = settings
        self._http = http or httpx.AsyncClient(timeout=20.0)

    async def _sol_price_usd(self) -> float:
        for t in await self._market.get_watchlist():
            if (t.symbol or "").upper() == "SOL" and t.price_usd:
                return t.price_usd
        raise ExternalServiceError("SOL price unavailable — cannot size the trade")

    async def _jupiter_quote(
        self, input_mint: str, output_mint: str, amount: int
    ) -> dict:
        res = await self._http.get(
            _QUOTE_URL,
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": self._risk.limits.max_slippage_bps,
            },
        )
        if res.status_code != 200 or "outAmount" not in res.text:
            raise ExternalServiceError("no Jupiter route for this token right now")
        return res.json()

    async def _build(self, quote: dict, user_pubkey: str) -> str:
        """POST the quote to Jupiter; get back the UNSIGNED transaction."""
        res = await self._http.post(
            _SWAP_URL,
            json={
                "quoteResponse": quote,
                "userPublicKey": user_pubkey,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto",
            },
        )
        body = res.json()
        tx = body.get("swapTransaction")
        if res.status_code != 200 or not tx:
            raise ExternalServiceError("Jupiter could not build the transaction")
        # Validate it's real base64 before handing it to the wallet.
        base64.b64decode(tx)
        return tx

    async def build_buy(self, user_pubkey: str, mint: str, usd_size: float) -> BuiltSwap:
        """Build a SOL -> token buy for ~usd_size (user signs in Phantom)."""
        if self._risk.kill_switch:
            raise ManualTradeBlocked("kill switch engaged — trading halted")
        cap = self._settings.manual_trade_max_usd
        if usd_size > cap:
            raise ManualTradeBlocked(
                f"trade ${usd_size:.2f} exceeds the ${cap:.0f} manual cap "
                "(raise MANUAL_TRADE_MAX_USD in backend/.env to change)"
            )
        sol_usd = await self._sol_price_usd()
        lamports = int(usd_size / sol_usd * 1_000_000_000)
        if lamports <= 0:
            raise ManualTradeBlocked("trade size rounds to zero SOL")
        quote = await self._jupiter_quote(_SOL_MINT, mint, lamports)
        tx = await self._build(quote, user_pubkey)
        impact = _impact_pct(quote)
        return BuiltSwap(
            swap_transaction_b64=tx,
            description=(
                f"Buy ~${usd_size:.2f} ({lamports / 1e9:.4f} SOL) of {mint[:6]}… "
                f"→ {quote.get('outAmount')} base units"
            ),
            price_impact_pct=impact,
            out_amount=str(quote.get("outAmount")),
        )

    async def build_sell(self, user_pubkey: str, mint: str) -> BuiltSwap:
        """Build a token -> SOL sell of the user's FULL balance."""
        if self._risk.kill_switch:
            raise ManualTradeBlocked("kill switch engaged — trading halted")
        raw, _decimals = await self._rpc.get_token_balance_raw(user_pubkey, mint)
        if raw <= 0:
            raise ManualTradeBlocked("wallet holds none of this token")
        quote = await self._jupiter_quote(mint, _SOL_MINT, raw)
        tx = await self._build(quote, user_pubkey)
        return BuiltSwap(
            swap_transaction_b64=tx,
            description=(
                f"Sell full balance of {mint[:6]}… ({raw} base units) → "
                f"{quote.get('outAmount')} lamports SOL"
            ),
            price_impact_pct=_impact_pct(quote),
            out_amount=str(quote.get("outAmount")),
        )

    async def aclose(self) -> None:
        await self._http.aclose()


def _impact_pct(quote: dict) -> float | None:
    raw = quote.get("priceImpactPct")
    try:
        return round(float(raw) * 100, 4) if raw is not None else None
    except (TypeError, ValueError):
        return None


_builder: ManualSwapBuilder | None = None


def get_swap_builder(
    settings: Settings, risk: RiskEngine, rpc: RpcClient, market: MarketManager
) -> ManualSwapBuilder:
    global _builder
    if _builder is None:
        _builder = ManualSwapBuilder(risk, rpc, market, settings)
    return _builder


async def close_swap_builder() -> None:
    global _builder
    if _builder is not None:
        await _builder.aclose()
        _builder = None
