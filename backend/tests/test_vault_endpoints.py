"""Vault notes endpoint tests — synthetic vault in tmp_path.

The security tests matter most here: the vault also holds .env files and
automation configs, so containment failures would leak secrets.
"""

import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_vault
from modules.vault import VaultService


@pytest.fixture()
def vault_client(tmp_path, settings: Settings) -> TestClient:
    memory = tmp_path / "10 Memory"
    memory.mkdir()
    (memory / "Training Log.md").write_text("# Training Log\n\nDay 1.", encoding="utf-8")
    (memory / "Memory Hub.md").write_text("# Memory Hub\n\nHub.", encoding="utf-8")
    (memory / "not-a-note.txt").write_text("invisible", encoding="utf-8")
    # Secrets that must never be reachable through the API:
    (tmp_path / ".env").write_text("SECRET=yes", encoding="utf-8")
    hidden = tmp_path / "09 Automation"
    hidden.mkdir()
    (hidden / "config.md").write_text("not allowlisted", encoding="utf-8")

    vault_settings = Settings(_env_file=None, vault_path=tmp_path, log_level="WARNING")
    app = create_app(settings)
    app.dependency_overrides[get_vault] = lambda: VaultService(vault_settings)
    with TestClient(app) as client:
        yield client


def test_dirs_reports_only_present_allowlisted(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/vault/dirs")
    assert res.status_code == 200
    assert res.json() == ["10 Memory"]  # Daily Notes/Dashboard absent in tmp vault


def test_list_notes_md_only(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/vault/notes?dir=10 Memory")
    assert res.status_code == 200
    names = {n["name"] for n in res.json()}
    assert names == {"Training Log", "Memory Hub"}  # .txt is invisible
    assert all(n["path"].startswith("10 Memory/") for n in res.json())


def test_read_note(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/vault/note?path=10 Memory/Training Log.md")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Training Log"
    assert "Day 1." in body["content"]


def test_non_allowlisted_dir_404s(vault_client: TestClient) -> None:
    assert vault_client.get("/api/v1/vault/notes?dir=09 Automation").status_code == 404
    assert (
        vault_client.get("/api/v1/vault/note?path=09 Automation/config.md").status_code
        == 404
    )


@pytest.mark.parametrize(
    "path",
    [
        "10 Memory/../.env",
        "../.env",
        "10 Memory/..%2F.env",
        "10 Memory/nested/deep.md",
        "10 Memory/Training Log.txt",
        "C:/Windows/win.ini",
    ],
)
def test_traversal_and_non_md_always_404(vault_client: TestClient, path: str) -> None:
    res = vault_client.get("/api/v1/vault/note", params={"path": path})
    assert res.status_code == 404
