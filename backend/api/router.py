"""Top-level API router — mounts every versioned sub-router.

Adding a new domain endpoint = add a router module under api/v1/ and
include it here. Nothing else changes (Open/Closed principle).
"""

from fastapi import APIRouter

from api.v1 import health, system

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])

# TODO(api): /market endpoints once modules/market lands (snapshots, watchlist)
# TODO(api): /vault endpoints once services/vault lands (notes bridge)
# TODO(api): /agents endpoints for agent status & reports (read-only first)
