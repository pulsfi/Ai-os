"""Solana module — READ-ONLY chain access.

Scope guard: no wallets, no signing, no transactions — those never enter
this module. `RpcClient` is the single place JSON-RPC lives, replacing the
4x duplicated rpc() helper documented in docs/IMPLEMENTATION_NOTES.md.

Public surface:
    from modules.solana import RpcClient, SolanaRpcError

Done: async client, typed responses, retry + endpoint failover, unit tests.
TODO(solana): rate-limit awareness (respect Retry-After on 429).
TODO(solana): websocket subscriptions for slot/account watch (Phase 2+).
"""

from modules.solana.client import (
    RpcClient,
    SolanaRpcError,
    close_rpc_client,
    get_rpc_client,
)

__all__ = ["RpcClient", "SolanaRpcError", "close_rpc_client", "get_rpc_client"]
