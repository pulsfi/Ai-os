"""Read-only agents service backed by the Obsidian vault.

The 7 agents live as markdown under `<vault>/04 Agents/<Name>/`:
    <Name>.md   — hub note with YAML frontmatter (status, created)
    Mission.md / Rules.md / Tasks.md / Memory.md / Reports.md

This service parses those files into typed API responses. It never
writes to the vault, and there is deliberately NO process runtime here:
start/stop/restart are gated until Stage 6 (Multi-Agent Automation)
opens — the API says so honestly instead of faking a running process.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from core.exceptions import NotFoundError
from models.schemas.agents import (
    AgentDetail,
    AgentReport,
    AgentSummary,
)

logger = logging.getLogger(__name__)

# Reports.md sections look like: "## Report: Helius RPC — 2026-07-02"
_REPORT_HEADING = re.compile(r"^##\s+Report:\s*(?P<title>.+?)\s*[—-]\s*(?P<date>\d{4}-\d{2}-\d{2})\s*$")
_FRONTMATTER_FIELD = re.compile(r"^(?P<key>[A-Za-z_]+):\s*(?P<value>.+?)\s*$")

# Fixed pipeline order (mirrors Agent Control Center.md)
_PIPELINE_ORDER = [
    "Research Agent",
    "Strategy Agent",
    "Risk Agent",
    "Execution Agent",
    "Monitoring Agent",
    "Learning Agent",
    "Documentation Agent",
]


class AgentsService:
    """Reads the agent pipeline state from vault markdown (read-only)."""

    def __init__(self, settings: Settings) -> None:
        # backend/ is the CWD; vault_path is relative to it.
        self._agents_root = (Path(settings.vault_path) / settings.agents_dir).resolve()

    # -- internal parsing ---------------------------------------------------

    def _agent_dirs(self) -> list[Path]:
        if not self._agents_root.is_dir():
            logger.warning("Agents dir not found: %s", self._agents_root)
            return []
        dirs = [p for p in self._agents_root.iterdir() if p.is_dir()]
        # Pipeline order first, anything unknown appended alphabetically.
        order = {name: i for i, name in enumerate(_PIPELINE_ORDER)}
        return sorted(dirs, key=lambda p: (order.get(p.name, len(order)), p.name))

    def _resolve_agent_dir(self, name: str) -> Path:
        """Resolve a client-supplied agent name to a real vault directory.

        Matches by exact directory name (case-insensitive) against the
        actual listing — never joins client input into a path directly,
        so traversal sequences cannot escape the agents root.
        """
        for d in self._agent_dirs():
            if d.name.lower() == name.strip().lower():
                return d
        raise NotFoundError(f"Unknown agent: {name}")

    @staticmethod
    def _read_frontmatter(md_file: Path) -> dict[str, str]:
        """Extract simple `key: value` pairs from YAML frontmatter."""
        fields: dict[str, str] = {}
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return fields
        if not text.startswith("---"):
            return fields
        for line in text.split("\n")[1:30]:
            if line.strip() == "---":
                break
            m = _FRONTMATTER_FIELD.match(line)
            if m:
                fields[m.group("key")] = m.group("value")
        return fields

    @staticmethod
    def _first_paragraph(md_file: Path) -> str:
        """First body paragraph after the H1 — used as the description."""
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return ""
        body: list[str] = []
        past_heading = False
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                past_heading = True
                continue
            if past_heading:
                if stripped and not stripped.startswith(("|", "#", "---")):
                    body.append(stripped)
                elif body:
                    break
        # Strip wikilink syntax for a clean plain-text description.
        text_out = " ".join(body)
        text_out = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text_out)
        return text_out

    def _parse_reports(self, agent_dir: Path) -> list[AgentReport]:
        """Split Reports.md into dated report entries (newest first)."""
        reports_file = agent_dir / "Reports.md"
        if not reports_file.is_file():
            return []
        try:
            lines = reports_file.read_text(encoding="utf-8").split("\n")
        except OSError:
            return []
        reports: list[AgentReport] = []
        current: AgentReport | None = None
        body: list[str] = []
        for line in lines:
            m = _REPORT_HEADING.match(line)
            if m:
                if current is not None:
                    current.body = "\n".join(body).strip()
                    reports.append(current)
                current = AgentReport(
                    title=m.group("title"), date=m.group("date"), body=""
                )
                body = []
            elif current is not None:
                body.append(line)
        if current is not None:
            current.body = "\n".join(body).strip()
            reports.append(current)
        reports.sort(key=lambda r: r.date, reverse=True)
        return reports

    def _last_activity(self, agent_dir: Path) -> datetime | None:
        """Most recent mtime across the agent's markdown files."""
        try:
            times = [f.stat().st_mtime for f in agent_dir.glob("*.md")]
        except OSError:
            return None
        if not times:
            return None
        return datetime.fromtimestamp(max(times), tz=timezone.utc)

    def _summary_for(self, agent_dir: Path) -> AgentSummary:
        hub = agent_dir / f"{agent_dir.name}.md"
        front = self._read_frontmatter(hub)
        reports = self._parse_reports(agent_dir)
        return AgentSummary(
            name=agent_dir.name,
            status=front.get("status", "unknown"),
            created=front.get("created"),
            description=self._first_paragraph(hub),
            report_count=len(reports),
            last_report_date=reports[0].date if reports else None,
            last_activity=self._last_activity(agent_dir),
        )

    # -- public API ----------------------------------------------------------

    def list_agents(self) -> list[AgentSummary]:
        """All agents in pipeline order, parsed from the vault."""
        return [self._summary_for(d) for d in self._agent_dirs()]

    def get_agent(self, name: str) -> AgentDetail:
        """Full detail for one agent: summary + mission + rules + tasks."""
        agent_dir = self._resolve_agent_dir(name)
        summary = self._summary_for(agent_dir)

        def read_section(filename: str) -> str:
            f = agent_dir / filename
            try:
                return f.read_text(encoding="utf-8") if f.is_file() else ""
            except OSError:
                return ""

        return AgentDetail(
            **summary.model_dump(),
            mission=read_section("Mission.md"),
            rules=read_section("Rules.md"),
            tasks=read_section("Tasks.md"),
        )

    def get_reports(self, name: str) -> list[AgentReport]:
        """The agent's report log, newest first (this is the 'logs' feed)."""
        return self._parse_reports(self._resolve_agent_dir(name))


_service: AgentsService | None = None


def get_agents_service(settings: Settings) -> AgentsService:
    """Process-wide singleton, same pattern as the other modules."""
    global _service
    if _service is None:
        _service = AgentsService(settings)
    return _service
