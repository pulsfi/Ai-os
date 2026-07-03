"""System information response contracts."""

from pydantic import BaseModel


class SystemInfo(BaseModel):
    """Static application identity returned by GET /system/info."""

    app_name: str
    version: str
    environment: str
    debug: bool
