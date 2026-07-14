"""Adaptive optimizer — regime classification, bounded params, the cooling
lock, honest insufficiency, and the validated-threshold-only rule."""

import time

from config import Settings
from modules.bots.optimizer import (
    AdaptiveOptimizer,
    RegimeMetrics,
    classify_mode,
    derive_params,
)


def metrics(**over) -> RegimeMetrics:
    base = dict(atr_pct=25.0, bb_width=0.2, relative_volume=1.0,
                buy_pressure=0.5, liquidity_usd=9_000.0,
                launches_last_hour=20, launches_analyzed=40)
    base.update(over)
    return RegimeMetrics(**base)


def test_mode_classification_is_deterministic() -> None:
    assert classify_mode(metrics(relative_volume=0.3, buy_pressure=0.3)) == "consolidation"
    assert classify_mode(metrics(atr_pct=10.0)) == "scalping"
    assert classify_mode(metrics(buy_pressure=0.7, relative_volume=1.5)) == "momentum"
    assert classify_mode(metrics()) == "launch"


def test_derived_params_scale_with_atr_and_stay_bounded() -> None:
    calm = derive_params("launch", metrics(atr_pct=10.0))
    wild = derive_params("launch", metrics(atr_pct=60.0))
    # Wider chop -> wider stops/trails, smaller size.
    assert wild["stop_loss_pct"] > calm["stop_loss_pct"]
    assert wild["trail_drop_pct"] > calm["trail_drop_pct"]
    assert wild["usd_per_trade"] < calm["usd_per_trade"]
    # Hard clamps hold even at absurd volatility.
    crazy = derive_params("launch", metrics(atr_pct=500.0))
    assert crazy["stop_loss_pct"] <= 30 and crazy["trail_drop_pct"] <= 15
    assert 20 <= crazy["usd_per_trade"] <= 80
    # Mode overlays apply.
    assert derive_params("consolidation", metrics())["max_open_positions"] == 2
    assert derive_params("scalping", metrics(atr_pct=10.0))["max_open_positions"] == 4


class _StubManager:
    def __init__(self) -> None:
        self.updates: list[tuple[str, dict]] = []

    def update_config(self, bot_id: str, update) -> None:
        self.updates.append((bot_id, update.model_dump(exclude_none=True)))


class _StubEngine:
    def __init__(self, ranked: list[dict]) -> None:
        self._ranked = ranked

    def rank(self) -> list[dict]:
        return self._ranked


class _StubRecorder:
    """N launches, each with a simple recorded path of the given swing."""

    def __init__(self, n: int, swing_pct: float = 30.0) -> None:
        now = time.time()
        self._launches = [
            {"mint": f"M{i}", "ts": now - 1800 - i * 60, "symbol": f"M{i}",
             "score": 60.0, "approved": 1, "mcap_usd": 9_000.0,
             "buyers": None, "top5_holders_pct": None}
            for i in range(n)
        ]
        self._swing = swing_pct

    def launches(self, window_days: float) -> list[dict]:
        return self._launches

    def path(self, mint: str, after_ts: float, horizon_s: float = 1200.0):
        e = 0.00001
        return [(after_ts + i * 30, p) for i, p in enumerate(
            [e, e * (1 + self._swing / 100), e * (1 + self._swing / 200)]
        )]


def optimizer(n_launches=40, ranked=None, tmp_path=None) -> tuple[AdaptiveOptimizer, _StubManager]:
    settings = Settings(
        _env_file=None,
        bots_overrides_path=str(tmp_path / "overrides.json"),
    )
    mgr = _StubManager()
    opt = AdaptiveOptimizer(mgr, _StubRecorder(n_launches), _StubEngine(ranked or []), settings)
    return opt, mgr


def test_insufficient_data_is_honest(tmp_path) -> None:
    opt, mgr = optimizer(n_launches=5, tmp_path=tmp_path)
    report = opt.optimize()
    assert report["applied"] is False
    assert "insufficient recorded data" in report["reason"]
    assert mgr.updates == []  # nothing touched


def test_optimize_applies_then_cooling_lock_blocks(tmp_path) -> None:
    opt, mgr = optimizer(tmp_path=tmp_path)
    first = opt.optimize()
    assert first["applied"] is True and len(mgr.updates) == 1
    bot_id, params = mgr.updates[0]
    assert bot_id == "sniper"
    assert 10 <= params["stop_loss_pct"] <= 30
    # Second automatic pass: LOCKED.
    second = opt.optimize()
    assert second["applied"] is False and "cooling lock" in second["reason"]
    assert len(mgr.updates) == 1
    # Explicit force overrides the lock (human decision).
    third = opt.optimize(force=True)
    assert third["applied"] is True and len(mgr.updates) == 2


def test_lock_survives_restart_via_state_file(tmp_path) -> None:
    opt, _ = optimizer(tmp_path=tmp_path)
    assert opt.optimize()["applied"] is True
    # A "restarted" optimizer over the same state file inherits the lock.
    opt2, mgr2 = optimizer(tmp_path=tmp_path)
    assert opt2.optimize()["applied"] is False
    assert mgr2.updates == []


def test_threshold_only_moves_to_validated_variant(tmp_path) -> None:
    # No validated variants -> min_confidence must NOT be in the update.
    opt, mgr = optimizer(ranked=[{"validated": False, "threshold": 40, "variant": "x"}],
                         tmp_path=tmp_path)
    opt.optimize()
    assert "min_confidence" not in mgr.updates[0][1]
    # A validated variant moves it.
    opt2, mgr2 = optimizer(
        ranked=[{"validated": True, "threshold": 60, "variant": "capture@60"}],
        tmp_path=tmp_path / "b",
    )
    (tmp_path / "b").mkdir(exist_ok=True)
    opt2.optimize()
    assert mgr2.updates[0][1]["min_confidence"] == 60.0
