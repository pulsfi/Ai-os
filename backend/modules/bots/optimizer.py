"""Adaptive strategy optimization — regime-driven, validated, and locked.

Every ~30 minutes (and on demand) the optimizer measures the CURRENT
launch-market regime from data the system records itself, classifies a
trading mode, derives bounded parameters for the sniper, applies them
through the normal validated config path, and then LOCKS for a cooling
period so parameters aren't chased tick-to-tick.

Honest indicator definitions (there is no single instrument here, so the
classic indicators are computed over the POPULATION of recorded launches):

* ATR%            — median per-launch true range: (high-low)/entry over
                    each recent launch's recorded path. Volatility of the
                    playing field.
* Bollinger width — dispersion (stdev) of per-launch net returns around
                    their mean: how spread out outcomes currently are.
* Relative volume — launches evaluated in the last hour vs. the window's
                    hourly average: is the market hot or quiet?
* Buy pressure    — blend of the approval rate and average confidence
                    score across recent evaluations (plus stream flow
                    health when available).
* Liquidity       — median market cap of evaluated launches (bonding-
                    curve depth proxy; labeled as such, never invented).

Safety rails:
* The ENTRY THRESHOLD only changes to a walk-forward VALIDATED value from
  the backtest engine. No validated variant -> threshold stays put.
* All derived parameters are hard-clamped to sane ranges.
* Changes go through BotManager.update_config (validated merge, persisted,
  live-applied) — the same path the Tune modal uses.
* A cooling lock (default 6h) blocks recalibration; force=True overrides
  it explicitly (logged), automatic runs never do.
"""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MODES = ("launch", "momentum", "scalping", "consolidation")


@dataclass
class RegimeMetrics:
    """The measured state of the launch market right now."""

    atr_pct: float | None = None
    bb_width: float | None = None
    relative_volume: float | None = None
    buy_pressure: float | None = None  # 0..1
    liquidity_usd: float | None = None
    launches_last_hour: int = 0
    launches_analyzed: int = 0


def classify_mode(m: RegimeMetrics) -> str:
    """Deterministic regime -> mode mapping (documented, testable)."""
    rv = m.relative_volume or 0.0
    atr = m.atr_pct or 0.0
    bp = m.buy_pressure or 0.0
    if rv < 0.6 and bp < 0.45:
        return "consolidation"  # quiet market, weak demand: sit back
    if atr < 18.0 and m.launches_analyzed >= 10:
        return "scalping"  # tame moves: tighter exits, more small bites
    if bp >= 0.55 and rv >= 1.0:
        return "momentum"  # hot tape with real demand behind it
    return "launch"  # default posture: fresh-launch sniping


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, round(v, 1)))


def derive_params(mode: str, m: RegimeMetrics) -> dict:
    """Bounded parameter set for the sniper, scaled by measured volatility.

    Stops/trails scale with ATR (wider chop needs wider stops or every
    position dies to noise; calm tape tightens them). Size targets roughly
    constant risk: high ATR -> smaller positions. Cooldown/max positions
    follow the mode. The profit-capture engine keeps owning the profit
    side when enabled — take_profit_pct still matters as its disabled-mode
    fallback and is set coherently anyway."""
    atr = m.atr_pct if m.atr_pct is not None else 25.0
    params = {
        "stop_loss_pct": _clamp(1.2 * atr, 10, 30),
        "take_profit_pct": _clamp(2.5 * atr, 25, 90),
        "trail_after_pct": _clamp(1.0 * atr, 8, 25),
        "trail_drop_pct": _clamp(0.6 * atr, 5, 15),
        "usd_per_trade": _clamp(50.0 * (25.0 / max(atr, 8.0)), 20, 80),
        "reentry_cooldown_s": 900.0,
        "max_open_positions": 3,
    }
    if mode == "momentum":
        params["reentry_cooldown_s"] = 300.0
        params["max_open_positions"] = 3
    elif mode == "scalping":
        params["take_profit_pct"] = _clamp(1.5 * atr, 15, 40)
        params["trail_drop_pct"] = _clamp(0.4 * atr, 4, 10)
        params["max_open_positions"] = 4
        params["reentry_cooldown_s"] = 600.0
    elif mode == "consolidation":
        params["max_open_positions"] = 2
        params["reentry_cooldown_s"] = 1200.0
        params["usd_per_trade"] = _clamp(params["usd_per_trade"] * 0.7, 15, 60)
    return params


class AdaptiveOptimizer:
    """Measures, classifies, derives, applies, locks. State survives
    restarts via a small JSON file next to the bot overrides."""

    def __init__(self, manager, recorder, engine, settings) -> None:
        self._manager = manager
        self._recorder = recorder
        self._engine = engine
        self._cooling_s = settings.optimizer_cooling_hours * 3600
        self._interval_s = settings.optimizer_interval_seconds
        self._enabled = settings.optimizer_enabled
        self._state_path = Path(settings.bots_overrides_path).parent / "optimizer_state.json"
        self._state: dict = self._load_state()
        self._task: asyncio.Task | None = None

    # -- persistence ---------------------------------------------------------

    def _load_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except OSError as exc:  # best-effort, like the overrides file
            logger.warning("optimizer state not persisted: %s", exc)

    # -- measurement ---------------------------------------------------------

    def measure(self, window_hours: float = 24.0) -> RegimeMetrics:
        """Compute the regime from recorded launches + paths (max 60)."""
        launches = self._recorder.launches(window_hours / 24.0)
        m = RegimeMetrics(launches_analyzed=len(launches))
        if not launches:
            return m
        now = time.time()
        m.launches_last_hour = sum(1 for l in launches if now - l["ts"] <= 3600)
        span_h = max((now - min(l["ts"] for l in launches)) / 3600, 1.0)
        hourly_avg = len(launches) / span_h
        m.relative_volume = round(m.launches_last_hour / hourly_avg, 2) if hourly_avg else None

        mcaps = [l["mcap_usd"] for l in launches if l.get("mcap_usd")]
        m.liquidity_usd = round(statistics.median(mcaps), 0) if mcaps else None

        scores = [l["score"] for l in launches]
        approvals = [l["approved"] for l in launches]
        m.buy_pressure = round(
            0.5 * (sum(scores) / len(scores) / 100.0) + 0.5 * (sum(approvals) / len(approvals)),
            2,
        )

        ranges: list[float] = []
        rets: list[float] = []
        for launch in launches[-60:]:
            path = self._recorder.path(launch["mint"], launch["ts"])
            if len(path) < 3:
                continue
            prices = [p for _, p in path]
            first = prices[0]
            if first <= 0:
                continue
            ranges.append((max(prices) - min(prices)) / first * 100)
            rets.append(prices[-1] / first - 1.0)
        if ranges:
            m.atr_pct = round(statistics.median(ranges), 1)
        if len(rets) >= 2:
            m.bb_width = round(statistics.stdev(rets), 3)
        return m

    # -- optimization --------------------------------------------------------

    @property
    def locked_until(self) -> float:
        return float(self._state.get("locked_until", 0.0))

    def optimize(self, force: bool = False) -> dict:
        """One full pass. Returns a report; applies only when allowed."""
        now = time.time()
        if not force and now < self.locked_until:
            return {
                "applied": False,
                "reason": f"cooling lock active until "
                f"{datetime.fromtimestamp(self.locked_until, tz=timezone.utc).isoformat(timespec='seconds')}",
                **self.status(),
            }
        metrics = self.measure()
        if metrics.launches_analyzed < 24 or metrics.atr_pct is None:
            return {
                "applied": False,
                "reason": f"insufficient recorded data "
                f"({metrics.launches_analyzed} launches; need >= 24 with paths)",
                "metrics": asdict(metrics),
                **self.status(),
            }
        mode = classify_mode(metrics)
        params = derive_params(mode, metrics)

        # Entry threshold: ONLY a walk-forward validated value may move it.
        threshold_note = "threshold unchanged (no validated variant)"
        try:
            ranked = self._engine.rank()
            validated = [r for r in ranked if r["validated"]]
            if validated:
                params["min_confidence"] = float(validated[0]["threshold"])
                threshold_note = (
                    f"threshold {validated[0]['threshold']:.0f} from validated "
                    f"variant {validated[0]['variant']}"
                )
        except Exception as exc:  # noqa: BLE001 — ranking failure must not block
            threshold_note = f"threshold unchanged (backtest unavailable: {exc})"

        from models.schemas.bots import BotConfigUpdate

        self._manager.update_config("sniper", BotConfigUpdate(**params))
        self._state = {
            "locked_until": now + self._cooling_s,
            "applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
            "metrics": asdict(metrics),
            "params": params,
            "threshold_note": threshold_note,
            "forced": force,
        }
        self._save_state()
        logger.info("optimizer applied %s mode: %s (%s)", mode, params, threshold_note)
        return {"applied": True, "reason": None, **self.status()}

    def status(self) -> dict:
        now = time.time()
        return {
            "enabled": self._enabled,
            "locked": now < self.locked_until,
            "locked_until": (
                datetime.fromtimestamp(self.locked_until, tz=timezone.utc).isoformat(
                    timespec="seconds"
                )
                if self.locked_until
                else None
            ),
            "last_applied_at": self._state.get("applied_at"),
            "mode": self._state.get("mode"),
            "metrics": self._state.get("metrics"),
            "params": self._state.get("params"),
            "threshold_note": self._state.get("threshold_note"),
        }

    # -- background loop -------------------------------------------------------

    def start(self) -> None:
        if self._enabled and (self._task is None or self._task.done()):
            self._task = asyncio.create_task(self._run(), name="adaptive-optimizer")
            logger.info("adaptive optimizer started (every %.0fs, cooling %.0fh)",
                        self._interval_s, self._cooling_s / 3600)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            try:
                report = self.optimize(force=False)
                if not report["applied"]:
                    logger.debug("optimizer pass skipped: %s", report["reason"])
            except Exception as exc:  # noqa: BLE001 — the loop must survive
                logger.warning("optimizer pass failed: %s", exc)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
