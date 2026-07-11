"""Confidence scorer — the sniper's risk/decision engine."""

from modules.bots.scoring import score_launch, score_pumpfun_launch

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


# --- pump.fun-native scorer (bonding-curve launches) ---------------------


def pump(**over):
    kw = dict(
        mcap_usd=18_000, mcap_growth_pct_per_min=15.0, bonding_progress_pct=12.0,
        reply_count=20, age_s=45, mint_revoked=True, freeze_revoked=True,
        min_mcap_usd=5_000, max_mcap_usd=60_000, max_age_s=300.0, min_confidence=55.0,
    )
    kw.update(over)
    return score_pumpfun_launch(**kw)


def test_pump_confirmed_climber_approved() -> None:
    """Revoked authorities + climbing cap + traction => passes the gate."""
    v = pump()
    assert v.approved is True and v.score >= 55 and not v.rejects


def test_pump_first_sighting_waits_for_confirmation() -> None:
    """No velocity yet (first sighting) => never bought on sight."""
    v = pump(mcap_growth_pct_per_min=None)
    assert v.approved is False
    assert any("confirm" in r.lower() for r in v.rejects)


def test_pump_flat_or_dumping_rejected() -> None:
    """A launch that isn't climbing has no buy pressure => reject."""
    v = pump(mcap_growth_pct_per_min=-5.0)
    assert v.approved is False
    assert any("buy pressure" in r.lower() for r in v.rejects)


def test_pump_active_mint_authority_hard_rejects() -> None:
    v = pump(mint_revoked=False)
    assert v.approved is False
    assert any("mint authority ACTIVE" in r for r in v.rejects)


def test_pump_below_floor_rejected() -> None:
    """No real buyers yet (cap under the floor) => stay out."""
    v = pump(mcap_usd=1_000)
    assert v.approved is False
    assert any("floor" in r.lower() for r in v.rejects)


def test_pump_snapshot_mode_scores_without_velocity() -> None:
    """Research-card mode: unknown velocity doesn't hard-reject, it just
    scores 0 on that factor so the card can still show a partial verdict."""
    v = pump(mcap_growth_pct_per_min=None, require_growth_confirmation=False)
    assert not any("confirm" in r.lower() for r in v.rejects)
    assert 0 <= v.score <= 100
    names = {f.name for f in v.factors}
    assert {"velocity", "bonding", "replies", "mcap"} <= names
