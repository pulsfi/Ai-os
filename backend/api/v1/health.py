"""Health endpoints.

- GET /health — full component report (monitoring dashboards, humans)
- GET /ping   — liveness probe (load balancers, k8s): no dependencies touched
"""

from fastapi import APIRouter

from core.dependencies import HealthServiceDep
from models.schemas.health import HealthReport

router = APIRouter()


@router.get("/health", response_model=HealthReport)
async def health(service: HealthServiceDep) -> HealthReport:
    """Probe every dependency and report aggregate system health."""
    return await service.check()


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Liveness: proves the process serves requests. Always cheap."""
    return {"status": "ok"}
