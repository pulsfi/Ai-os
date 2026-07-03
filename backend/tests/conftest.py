"""Shared test fixtures.

Tests build their own app instance via the factory — no import-time
globals, no shared state between test modules.
"""

import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app


@pytest.fixture()
def settings() -> Settings:
    """Deterministic settings for tests (no .env interference)."""
    return Settings(_env_file=None, debug=True, log_level="WARNING")


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    """HTTP client against a freshly-wired application."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
