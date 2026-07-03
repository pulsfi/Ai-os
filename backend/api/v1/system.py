"""System endpoints — application identity and runtime configuration."""

from fastapi import APIRouter

from core.dependencies import SettingsDep
from models.schemas.system import SystemInfo

router = APIRouter()


@router.get("/info", response_model=SystemInfo)
async def system_info(settings: SettingsDep) -> SystemInfo:
    """Return non-sensitive application identity (name, version, env)."""
    return SystemInfo(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment.value,
        debug=settings.debug,
    )
