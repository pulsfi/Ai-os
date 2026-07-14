"""Capture-replay backtesting.

The recorder persists what the live system actually observes (launch
features at decision time + the mcap path that follows); the engine
replays those recordings against strategy variants. No synthetic or
purchased history — backtests run on the same data the bots traded on.
"""

from modules.backtest.engine import BacktestEngine
from modules.backtest.recorder import MarketRecorder, get_recorder

__all__ = ["BacktestEngine", "MarketRecorder", "get_recorder"]
