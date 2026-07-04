"""Trading module — READ-ONLY bridge to the paper-trading ledger.

The Node automation layer (09 Automation/market/) runs the paper scalper
and owns the SQLite ledger; this module only reads it so the API and UI
can show the track record. No live execution exists anywhere in this
repo — that is the roadmap's Stage 5 gate.

Public surface:
    PaperTradingService       — portfolio summary + trade log (read-only)
    get_paper_trading_service — process-wide singleton accessor
"""

from modules.trading.paper_service import (
    PaperTradingService,
    get_paper_trading_service,
)

__all__ = ["PaperTradingService", "get_paper_trading_service"]
