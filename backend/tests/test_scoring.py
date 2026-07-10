"""Confidence scorer — the sniper's risk/decision engine."""

from modules.bots.scoring import score_launch

BASE = dict(min_mcap_usd=5_000, max_mcap_usd=60_000, max_age_s=300.0, min_confidence=55.0)


def strong(**over):
    kw = dict(
        mcap_usd=20_000, age_s=30, mint_revoked=True, freeze_revoked=True,
        buy_ratio_pct=80.0, unique_wallets=15, swaps=20, **BASE,
    )
    kw.update(over)
    return score_launch(**kw)


def test_strong_launch_approved() -> None:
    v = strong()
    assert v.approved is True
    assert v.score >= 55
    assert not v.rejects


def test_active_mint_authority_hard_rejects() -> None:
    v = strong(mint_revoked=False)
    assert v.approved is False
    assert any("mint authority ACTIVE" in r for r in v.rejects)


def test_active_freeze_authority_hard_rejects() -> None:
    v = strong(freeze_revoked=False)
    assert v.approved is False
    assert any("freeze" in r.lower() for r in v.rejects)


def test_net_selling_rejected() -> None:
    v = strong(buy_ratio_pct=25.0, unique_wallets=4, swaps=5)
    assert v.approved is False


def test_missing_flow_cannot_reach_threshold() -> None:
    """No demand data -> stay out (reject if info missing)."""
    v = strong(buy_ratio_pct=None, unique_wallets=None, swaps=None)
    assert v.approved is False
    assert v.score < 55


def test_score_bounded_and_explained() -> None:
    v = strong()
    assert 0 <= v.score <= 100
    names = {f.name for f in v.factors}
    assert {"mint", "freeze", "buy_ratio", "wallets", "swaps", "mcap", "age"} <= names
    assert "confidence" in v.note()
