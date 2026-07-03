"""Settings behavior: defaults, environment overrides, derived values."""

from config import Settings
from config.settings import Environment


def test_defaults_are_safe() -> None:
    """With no environment at all, settings must be valid and development-mode."""
    s = Settings(_env_file=None)
    assert s.environment is Environment.DEVELOPMENT
    assert s.is_production is False
    assert s.api_v1_prefix == "/api/v1"


def test_env_override(monkeypatch) -> None:
    """Environment variables take priority over defaults."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_JSON", "true")
    s = Settings(_env_file=None)
    assert s.is_production is True
    assert s.log_json is True


def test_helius_key_upgrades_rpc_url() -> None:
    """A Helius key must transparently upgrade the effective RPC endpoint."""
    s = Settings(_env_file=None, helius_api_key="test-key")
    assert "helius" in s.rpc_url
    assert "test-key" in s.rpc_url


def test_no_key_keeps_public_rpc() -> None:
    """Without a key, the configured public endpoint is used unchanged."""
    s = Settings(_env_file=None)
    assert s.rpc_url == s.solana_rpc_url
