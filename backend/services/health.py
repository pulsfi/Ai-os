"""Health service — probes every infrastructure dependency concurrently.

Semantics:
- `api` is always ok if this code runs.
- `database` / `redis` are OPTIONAL in development: their failure degrades
  the system (status "degraded") but does not fail the endpoint.
- `solana_rpc` is an external read-only dependency, probed with getHealth.

Every probe is time-boxed so a hung dependency can never hang /health.
"""

import asyncio
import logging
import time

import httpx
from sqlalchemy import text

from config import Settings
from database.engine import get_engine
from database.redis_client import get_redis
from models.schemas.health import ComponentStatus, HealthReport, Status

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 2.5


class HealthService:
    """Aggregates component probes into one HealthReport."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> HealthReport:
        """Probe all components in parallel and compute overall status."""
        components = await asyncio.gather(
            self._probe("database", self._check_database),
            self._probe("redis", self._check_redis),
            self._probe("solana_rpc", self._check_solana_rpc),
        )
        overall = Status.OK if all(c.status is Status.OK for c in components) else Status.DEGRADED
        return HealthReport(
            status=overall,
            version=self._settings.app_version,
            environment=self._settings.environment.value,
            components=[ComponentStatus(name="api", status=Status.OK), *components],
        )

    async def _probe(self, name: str, fn) -> ComponentStatus:
        """Run one probe with a timeout; convert failures into DOWN status."""
        start = time.perf_counter()
        try:
            await asyncio.wait_for(fn(), timeout=PROBE_TIMEOUT_S)
            latency = (time.perf_counter() - start) * 1000
            return ComponentStatus(name=name, status=Status.OK, latency_ms=round(latency, 1))
        except Exception as exc:  # noqa: BLE001 — a probe must never raise
            logger.debug("health probe %s failed: %s", name, exc)
            # str(exc) alone is empty for TimeoutError & friends — always
            # include the class name so the report stays diagnosable.
            detail = f"{type(exc).__name__}: {exc}".rstrip(": ").strip()
            return ComponentStatus(name=name, status=Status.DOWN, detail=detail[:200])

    async def _check_database(self) -> None:
        """SELECT 1 through the async engine proves connectivity + auth."""
        engine = get_engine(self._settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def _check_redis(self) -> None:
        """PING proves the Redis connection pool is alive."""
        await get_redis(self._settings).ping()

    async def _check_solana_rpc(self) -> None:
        """JSON-RPC getHealth against the configured Solana endpoint."""
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
            res = await client.post(
                self._settings.rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
            )
            res.raise_for_status()
