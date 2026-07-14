"""Capture-replay backtesting: recorder, candles, engine metrics, ranking,
and walk-forward validation. All data is seeded locally — no network."""

import time

from modules.backtest.engine import BacktestEngine
from modules.backtest.recorder import MarketRecorder


def make_recorder(tmp_path) -> MarketRecorder:
    return MarketRecorder(tmp_path / "bt.db", retention_days=5.0)


def seed_launch(
    rec: MarketRecorder,
    mint: str,
    score: float,
    path_pcts: list[float],
    t0: float,
    entry_mcap: float = 10_000.0,
    step_s: float = 30.0,
) -> None:
    """One recorded launch: a snapshot at t0 plus its later price path.
    path_pcts are gains relative to entry (e.g. 10 = +10%)."""
    rec.snapshot(mint, mint[:5], score, True, entry_mcap)
    # snapshot() stamps now; overwrite ts directly for deterministic replay.
    with rec._connect() as conn:
        conn.execute("UPDATE launch_snapshots SET ts = ? WHERE mint = ?", (t0, mint))
        for i, pct in enumerate(path_pcts):
            price = (entry_mcap / 1e9) * (1 + pct / 100)
            conn.execute(
                "INSERT INTO price_samples (mint, ts, price_usd) VALUES (?, ?, ?)",
                (mint, t0 + (i + 1) * step_s, price),
            )


def test_recorder_samples_throttle_and_candles(tmp_path) -> None:
    rec = make_recorder(tmp_path)
    rec.sample("M1", 0.00001)
    rec.sample("M1", 0.00002)  # inside the 10s throttle window -> dropped
    with rec._connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM price_samples").fetchone()["n"]
    assert n == 1
    # Candles aggregate raw samples into timeframe buckets. Align t0 to a
    # 1m bucket so all four samples (spanning 45s) land in ONE candle
    # regardless of wall-clock phase.
    t0 = (int(time.time()) // 60) * 60 - 600
    with rec._connect() as conn:
        for i, p in enumerate([1.0, 1.2, 0.9, 1.1]):
            conn.execute(
                "INSERT INTO price_samples (mint, ts, price_usd) VALUES (?, ?, ?)",
                ("M2", t0 + i * 15, p),
            )
    candles = rec.candles("M2", "1m")
    assert candles and candles[0]["high"] == 1.2 and candles[0]["low"] == 0.9
    assert candles[0]["open"] == 1.0
    assert sum(c["samples"] for c in candles) == 4


def test_recorder_prunes_beyond_window(tmp_path) -> None:
    rec = MarketRecorder(tmp_path / "bt.db", retention_days=1.0)
    old = time.time() - 3 * 86400
    with rec._connect() as conn:
        conn.execute(
            "INSERT INTO price_samples (mint, ts, price_usd) VALUES ('Old', ?, 1.0)", (old,)
        )
    rec._last_prune = 0.0
    rec._maybe_prune(time.time())
    with rec._connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM price_samples").fetchone()["n"]
    assert n == 0


def seed_world(rec: MarketRecorder, n_per_kind: int = 24) -> None:
    """A deterministic recorded world: high scorers run, low scorers dump.
    Timestamps spread chronologically for walk-forward folds — large enough
    that every fold's train side clears the engine's min-trades floor."""
    base = time.time() - 4 * 86400
    for i in range(n_per_kind):
        t = base + i * 3600
        # Good: high score, climbs steadily to +60% then holds.
        seed_launch(rec, f"GOOD{i}pump", 70 + (i % 5), [5, 12, 25, 40, 60, 55, 50], t)
        # Bad: low score, pumps a little then dumps hard.
        seed_launch(rec, f"BAD{i}pump", 45 + (i % 5), [4, -10, -35, -60], t + 3600)


def test_engine_metrics_and_threshold_separation(tmp_path) -> None:
    rec = make_recorder(tmp_path)
    seed_world(rec)
    engine = BacktestEngine(rec)
    launches = rec.launches(5.0)
    high = engine.metrics(engine._trades_for(launches, 65, "fixed"))
    low = engine.metrics(engine._trades_for(launches, 40, "fixed"))
    # Threshold 65 trades only the runners -> profitable; 40 takes the dumps.
    assert high["trades"] > 0 and high["net_profit_usd"] > 0
    assert low["trades"] > high["trades"]
    assert low["expectancy_usd"] < high["expectancy_usd"]
    for key in ("profit_factor", "win_rate_pct", "sharpe", "max_drawdown_usd", "expectancy_usd"):
        assert key in high


def test_ranking_orders_by_expectancy_and_flags_validation(tmp_path) -> None:
    rec = make_recorder(tmp_path)
    seed_world(rec)
    ranked = BacktestEngine(rec).rank(thresholds=(40, 65), exit_modes=("fixed", "capture"))
    assert len(ranked) == 4
    exps = [r["expectancy_usd"] for r in ranked if r["expectancy_usd"] is not None]
    assert exps == sorted(exps, reverse=True)  # ranked best first
    assert all("validated" in r for r in ranked)


def test_walk_forward_validates_only_with_consistent_oos_edge(tmp_path) -> None:
    rec = make_recorder(tmp_path)
    seed_world(rec)
    report = BacktestEngine(rec).walk_forward(exit_mode="fixed", thresholds=(40, 65))
    assert report["folds"], "expected folds on seeded data"
    # The seeded world has a real, stable edge at threshold 65 -> validated.
    assert report["validated"] is True
    for fold in report["folds"]:
        assert fold["chosen_threshold"] == 65


def test_walk_forward_honest_on_insufficient_data(tmp_path) -> None:
    rec = make_recorder(tmp_path)
    seed_launch(rec, "ONLYpump", 70, [5, 10], time.time() - 3600)
    report = BacktestEngine(rec).walk_forward()
    assert report["validated"] is False
    assert "insufficient data" in (report["reason"] or "")
