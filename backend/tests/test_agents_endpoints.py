"""Agents endpoint tests — run against a synthetic vault in tmp_path,
so they never depend on (or touch) the real Obsidian vault."""

import pytest
from fastapi.testclient import TestClient

from config import Settings
from core.application import create_app
from core.dependencies import get_agents
from modules.agents import AgentsService

_HUB = """---
tags: [agent, research]
status: active
created: 2026-07-02
---

# 🔬 Research Agent

Discovers new information across the [[Solana]] ecosystem.

| File | Purpose |
|---|---|
| [[Mission]] | Why |
"""

_REPORTS = """---
tags: [agent, research, reports]
---

# Reports — Research Agent

## Report: First Finding — 2026-07-01

Body of the first report.

## Report: Second Finding — 2026-07-02

Body of the second report.
"""


@pytest.fixture()
def vault_client(tmp_path, settings: Settings) -> TestClient:
    """App wired to a two-agent synthetic vault."""
    agents_dir = tmp_path / "04 Agents"
    research = agents_dir / "Research Agent"
    research.mkdir(parents=True)
    (research / "Research Agent.md").write_text(_HUB, encoding="utf-8")
    (research / "Reports.md").write_text(_REPORTS, encoding="utf-8")
    (research / "Mission.md").write_text("# Mission\n\nFind things.", encoding="utf-8")

    idle = agents_dir / "Strategy Agent"
    idle.mkdir()
    (idle / "Strategy Agent.md").write_text(
        "---\nstatus: standby\n---\n\n# Strategy Agent\n\nPlans trades.",
        encoding="utf-8",
    )

    vault_settings = Settings(_env_file=None, vault_path=tmp_path, log_level="WARNING")
    app = create_app(settings)
    app.dependency_overrides[get_agents] = lambda: AgentsService(vault_settings)
    with TestClient(app) as client:
        yield client


def test_list_agents_pipeline_order_and_status(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/agents")
    assert res.status_code == 200
    agents = res.json()
    assert [a["name"] for a in agents] == ["Research Agent", "Strategy Agent"]
    research = agents[0]
    assert research["status"] == "active"
    assert research["report_count"] == 2
    assert research["last_report_date"] == "2026-07-02"
    # Wikilink syntax is stripped from descriptions.
    assert "[[" not in research["description"]
    assert "Solana" in research["description"]


def test_agent_detail_includes_sections(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/agents/Research Agent")
    assert res.status_code == 200
    body = res.json()
    assert "Find things." in body["mission"]
    assert body["rules"] == ""  # file absent → empty, not invented


def test_agent_reports_newest_first(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/agents/Research Agent/reports")
    assert res.status_code == 200
    reports = res.json()
    assert [r["title"] for r in reports] == ["Second Finding", "First Finding"]
    assert "first report" in reports[1]["body"]


def test_unknown_agent_404s(vault_client: TestClient) -> None:
    res = vault_client.get("/api/v1/agents/Nope Agent")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_traversal_names_are_rejected(vault_client: TestClient) -> None:
    """Path-like names never resolve — lookups match real dirs only."""
    res = vault_client.get("/api/v1/agents/..%2F..%2Fsecrets")
    assert res.status_code == 404


def test_control_declines_honestly(vault_client: TestClient) -> None:
    """start/stop/restart answer with accepted=False + reason (no runtime)."""
    for action in ("start", "stop", "restart"):
        res = vault_client.post(f"/api/v1/agents/Research Agent/{action}")
        assert res.status_code == 200
        body = res.json()
        assert body["accepted"] is False
        assert body["action"] == action
        assert "runtime" in body["reason"].lower()


def test_control_rejects_unknown_action(vault_client: TestClient) -> None:
    assert (
        vault_client.post("/api/v1/agents/Research Agent/explode").status_code == 422
    )
