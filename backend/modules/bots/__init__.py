"""Bot fleet — multiple paper-trading bots running live inside the backend.

Each bot is an asyncio loop: fetch live market data → evaluate its
strategy → open/close VIRTUAL positions in a local SQLite ledger.

PAPER MODE ONLY. This package must never hold keys, sign transactions,
or touch a wallet — live execution stays behind the Stage 5 gate until
the paper track record justifies opening it.

Public surface:
    BotManager, get_bot_manager, close_bot_manager
"""

from modules.bots.manager import BotManager, close_bot_manager, get_bot_manager

__all__ = ["BotManager", "close_bot_manager", "get_bot_manager"]
