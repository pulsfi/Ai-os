"""Execution layer (Stage 5) — the safe foundation for live trading.

Ships DISARMED. Contains the risk engine, a dry-run executor (real
quotes, zero signing), and the go-live readiness scorecard. There is NO
private key handling and NO transaction signing in this package. The
real-money path is intentionally a guarded stub until the paper record
justifies building it — see modules/execution/executor.py.
"""

from modules.execution.executor import (
    DryRunExecutor,
    close_executor,
    get_executor,
)
from modules.execution.readiness import evaluate_readiness
from modules.execution.risk_engine import RiskEngine, get_risk_engine

__all__ = [
    "DryRunExecutor",
    "RiskEngine",
    "close_executor",
    "evaluate_readiness",
    "get_executor",
    "get_risk_engine",
]
