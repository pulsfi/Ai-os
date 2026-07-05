"""Go-live readiness scorecard.

Turns "is the bot good enough for real money?" from a gut feeling into a
checklist. Every criterion must pass before live execution is justified.
The numbers are deliberately conservative — the cost of going live too
early (real losses) dwarfs the cost of waiting a few more days.
"""

from datetime import datetime, timezone

from config import Settings
from models.schemas.bots import BotPerformance
from models.schemas.execution import GoLiveReadiness, ReadinessCriterion


def _days_since(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        start = datetime.fromisoformat(iso)
    except ValueError:
        return 0.0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - start).total_seconds() / 86_400


def evaluate_readiness(
    fleet: BotPerformance | None,
    first_entry_ts: str | None,
    settings: Settings,
) -> GoLiveReadiness:
    """Score the paper record against the go-live gates."""
    closed = fleet.closed_trades if fleet else 0
    win_rate = fleet.win_rate_pct if fleet and fleet.win_rate_pct is not None else 0.0
    pnl = fleet.realized_pnl_usd if fleet else 0.0
    days = _days_since(first_entry_ts)

    criteria = [
        ReadinessCriterion(
            name="Sample size",
            target=f">= {settings.golive_min_closed_trades} closed trades",
            actual=f"{closed} closed",
            passed=closed >= settings.golive_min_closed_trades,
        ),
        ReadinessCriterion(
            name="Win rate",
            target=f">= {settings.golive_min_win_rate_pct}%",
            actual=f"{win_rate}%",
            passed=win_rate >= settings.golive_min_win_rate_pct,
        ),
        ReadinessCriterion(
            name="Profitability",
            target=f"realized PnL >= ${settings.golive_min_realized_pnl_usd:.2f}",
            actual=f"${pnl:.2f}",
            passed=pnl >= settings.golive_min_realized_pnl_usd,
        ),
        ReadinessCriterion(
            name="Track length",
            target=f">= {settings.golive_min_days} days of record",
            actual=f"{days:.1f} days",
            passed=days >= settings.golive_min_days,
        ),
    ]
    ready = all(c.passed for c in criteria)
    n_pass = sum(c.passed for c in criteria)
    summary = (
        "All gates green — a small, capped live trial is now justifiable. "
        "Arming is still a deliberate, operator-only step."
        if ready
        else f"{n_pass}/{len(criteria)} gates green. Real money stays off until all pass."
    )
    return GoLiveReadiness(ready=ready, criteria=criteria, summary=summary)
