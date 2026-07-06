"""Risk engine — the gate every order must pass before it can execute.

Independent of whether execution is dry-run or (someday) live: the same
limits apply. Denials are the default; an order executes only when the
engine explicitly allows it. Tracks realized loss per UTC day and halts
trading for the rest of the day once the loss limit is hit.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import Settings
from core.exceptions import AppError
from models.schemas.execution import RiskLimits

logger = logging.getLogger(__name__)


class NotReadyForLive(AppError):
    """Arming live was refused — the go-live scorecard is not green."""

    status_code = 409
    code = "not_ready_for_live"


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


@dataclass
class RiskEngine:
    """Enforces position, loss, concurrency, and kill-switch limits."""

    limits: RiskLimits
    armed: bool
    _kill_switch: bool = False
    _day: str = ""
    _realized_today: float = 0.0
    _open_positions: int = 0
    _listeners: list = field(default_factory=list)

    def _roll_day(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._day:
            self._day = today
            self._realized_today = 0.0

    @property
    def realized_today(self) -> float:
        self._roll_day()
        return round(self._realized_today, 2)

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    def set_kill_switch(self, on: bool) -> None:
        """Operator halt/resume — only ever HALTS execution, never trades."""
        self._kill_switch = on
        logger.warning("execution kill switch %s", "ENGAGED" if on else "released")

    def set_armed(self, on: bool) -> None:
        """Flip the master arm state (paper ⇄ live intent).

        Arming does NOT create a real-money path for the bots — there is
        no signing key anywhere. It flips the execution engine's arm flag,
        which the gate above checks. Callers must enforce the readiness
        scorecard before arming live.
        """
        self.armed = on
        logger.warning("execution %s", "ARMED (live intent)" if on else "disarmed (paper)")

    def check_order(self, usd_size: float, side: str) -> RiskDecision:
        """The one gate. Returns allow/deny with a plain reason."""
        self._roll_day()
        if self._kill_switch:
            return RiskDecision(False, "kill switch engaged — all execution halted")
        if not self.armed:
            return RiskDecision(
                False, "execution disarmed (EXECUTION_ARMED is not true)"
            )
        if usd_size <= 0:
            return RiskDecision(False, "order size must be positive")
        if usd_size > self.limits.max_position_usd:
            return RiskDecision(
                False,
                f"size ${usd_size:.2f} exceeds max position ${self.limits.max_position_usd:.2f}",
            )
        if self._realized_today <= -abs(self.limits.daily_loss_limit_usd):
            return RiskDecision(
                False,
                f"daily loss limit hit (${self._realized_today:.2f}) — halted until tomorrow",
            )
        if side == "buy" and self._open_positions >= self.limits.max_concurrent_positions:
            return RiskDecision(
                False,
                f"already at max {self.limits.max_concurrent_positions} concurrent positions",
            )
        return RiskDecision(True, "within all risk limits")

    def record_open(self) -> None:
        self._open_positions += 1

    def record_close(self, realized_pnl_usd: float) -> None:
        self._roll_day()
        self._open_positions = max(0, self._open_positions - 1)
        self._realized_today += realized_pnl_usd
        if self._realized_today <= -abs(self.limits.daily_loss_limit_usd):
            logger.warning(
                "daily loss limit reached (%.2f); execution halts until tomorrow",
                self._realized_today,
            )


def limits_from_settings(settings: Settings) -> RiskLimits:
    return RiskLimits(
        max_position_usd=settings.exec_max_position_usd,
        daily_loss_limit_usd=settings.exec_daily_loss_limit_usd,
        max_concurrent_positions=settings.exec_max_concurrent_positions,
        max_slippage_bps=settings.exec_max_slippage_bps,
    )


_engine: RiskEngine | None = None


def get_risk_engine(settings: Settings) -> RiskEngine:
    """Process-wide singleton, same pattern as the other modules."""
    global _engine
    if _engine is None:
        _engine = RiskEngine(
            limits=limits_from_settings(settings),
            armed=settings.execution_armed,
        )
    return _engine
