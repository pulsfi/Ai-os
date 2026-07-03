"""Solana module — READ-ONLY chain access.

Scope guard (foundation phase): no wallets, no signing, no transactions.
This module is the single place JSON-RPC calls will live, ending the
current 4x duplication of the rpc() helper in the Node layer.

TODO(solana): async RpcClient (httpx) — getHealth, getSlot, getEpochInfo,
              getRecentPerformanceSamples, getAccountInfo, getTokenSupply,
              getTokenLargestAccounts (port from 09 Automation/market/sources/rpc.mjs
              and risk-engine.mjs).
TODO(solana): typed response models in models/schemas (EpochInfo, ChainStatus).
TODO(solana): retry policy + endpoint failover (public -> Helius).
TODO(solana): unit tests with mocked transport.
"""
