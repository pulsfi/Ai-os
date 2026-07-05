"""Daily-report writer tests — the vault's single write path."""

from pathlib import Path

from config import Settings
from models.schemas.bots import BotConfig, BotPerformance, BotState, BotStatus
from modules.vault import VaultService
from modules.vault.daily_report import build_daily_report


def make_status(bot_id: str, name: str) -> BotStatus:
    return BotStatus(
        config=BotConfig(
            id=bot_id,
            name=name,
            strategy="s",
            description="d",
            interval_s=20,
            usd_per_trade=50,
            max_open_positions=3,
            take_profit_pct=40,
            stop_loss_pct=25,
            max_hold_s=900,
        ),
        state=BotState.RUNNING,
        open_positions=1,
        closed_trades=2,
    )


def make_perf(bot_id: str, name: str, pnl: float) -> BotPerformance:
    return BotPerformance(
        bot_id=bot_id,
        name=name,
        closed_trades=2,
        wins=1,
        losses=1,
        win_rate_pct=50.0,
        realized_pnl_usd=pnl,
        avg_pnl_pct=1.5,
    )


def test_report_markdown_contains_fleet_table() -> None:
    md = build_daily_report(
        [make_status("trend", "Trend Scalper")],
        [make_perf("fleet", "Whole fleet", 3.21), make_perf("trend", "Trend Scalper", 3.21)],
    )
    assert "## Bot Fleet Report (auto)" in md
    assert "[[Documentation Agent]]" in md
    assert "| Trend Scalper | running | 1 | 2 | 50.0% | $+3.21 | +1.50% |" in md
    assert "**Fleet total:** 2 closed, 1W/1L, realized $+3.21." in md


def test_append_creates_todays_note_with_conventions(tmp_path: Path) -> None:
    service = VaultService(Settings(_env_file=None, vault_path=tmp_path))
    rel = service.append_daily_report("## Bot Fleet Report (auto)\n\ncontent")
    file = tmp_path / rel
    assert file.is_file() and rel.startswith("12 Daily Notes/")
    text = file.read_text(encoding="utf-8")
    # New note gets the vault's daily frontmatter + H1, then the section.
    assert text.startswith("---\ntags: [daily]\n")
    assert "← Back to [[Home]]" in text
    assert text.rstrip().endswith("content")


def test_append_is_additive_not_destructive(tmp_path: Path) -> None:
    service = VaultService(Settings(_env_file=None, vault_path=tmp_path))
    rel = service.append_daily_report("first section")
    existing = (tmp_path / rel).read_text(encoding="utf-8")
    service.append_daily_report("second section")
    after = (tmp_path / rel).read_text(encoding="utf-8")
    assert after.startswith(existing)  # nothing was overwritten
    assert "first section" in after and "second section" in after
