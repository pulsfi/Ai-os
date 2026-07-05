"""Daily bot-fleet report formatter — markdown for the vault's daily note.

Pure formatting: performance numbers in, vault-flavored markdown out
(wikilinks to the Documentation Agent and Trading pages keep the graph
connected). No I/O here; VaultService owns the single write path.
"""

from datetime import datetime, timezone

from models.schemas.bots import BotPerformance, BotStatus


def build_daily_report(
    statuses: list[BotStatus], performance: list[BotPerformance]
) -> str:
    """Render the fleet's day as a daily-note section."""
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines = [
        "## Bot Fleet Report (auto)",
        "",
        f"Written by the [[Documentation Agent]] at {now} · "
        "paper mode (virtual USD) · details in the Trading page",
        "",
        "| Bot | State | Open | Closed | Win rate | Realized PnL | Avg trade |",
        "|---|---|---|---|---|---|---|",
    ]
    perf_by_id = {p.bot_id: p for p in performance}
    for status in statuses:
        p = perf_by_id.get(status.config.id)
        win = f"{p.win_rate_pct}%" if p and p.win_rate_pct is not None else "—"
        avg = f"{p.avg_pnl_pct:+.2f}%" if p and p.avg_pnl_pct is not None else "—"
        pnl = f"${p.realized_pnl_usd:+.2f}" if p else "$0.00"
        lines.append(
            f"| {status.config.name} | {status.state.value} | "
            f"{status.open_positions} | {status.closed_trades} | "
            f"{win} | {pnl} | {avg} |"
        )
    fleet = perf_by_id.get("fleet")
    if fleet is not None:
        lines += [
            "",
            f"**Fleet total:** {fleet.closed_trades} closed, "
            f"{fleet.wins}W/{fleet.losses}L, realized "
            f"${fleet.realized_pnl_usd:+.2f}.",
        ]
    return "\n".join(lines)
