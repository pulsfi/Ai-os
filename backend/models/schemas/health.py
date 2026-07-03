"""Health check response contracts."""

from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Health of one component or of the system overall."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class ComponentStatus(BaseModel):
    """Result of probing a single dependency."""

    name: str = Field(description="Component identifier, e.g. 'database'")
    status: Status
    latency_ms: float | None = Field(default=None, description="Probe round-trip time")
    detail: str | None = Field(default=None, description="Error info when not ok")


class HealthReport(BaseModel):
    """Aggregate system health returned by GET /health."""

    status: Status = Field(description="ok = all up; degraded = optional deps down")
    version: str
    environment: str
    components: list[ComponentStatus]
