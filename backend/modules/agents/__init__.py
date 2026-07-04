"""Agents module — read-only bridge to the vault's 7-agent pipeline.

The agent definitions (Mission/Rules/Tasks/Memory/Reports) live as
Markdown in the vault (`04 Agents/`); this module parses them into the
typed /agents API while the vault stays the human-readable source of truth.

Public surface:
    AgentsService       — lists agents, reads status/mission/reports from markdown
    get_agents_service  — process-wide singleton accessor

TODO(agents): executable runtime (start/stop/restart) stays gated until
              Stage 6 (Multi-Agent Automation); the control endpoint
              reports "runtime not available" honestly until then.
TODO(agents): explicit gate — Execution Agent stays read-only until the
              paper-trading track record justifies Stage 5 (see roadmap).
"""

from modules.agents.agents_service import AgentsService, get_agents_service

__all__ = ["AgentsService", "get_agents_service"]
