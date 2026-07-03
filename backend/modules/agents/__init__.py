"""Agents module — runtime for the seven-agent system.

The agent definitions (Mission/Rules/Tasks/Memory/Reports) live as
Markdown in the vault (`04 Agents/`); this module will give them an
executable runtime while the vault stays the human-readable source
of truth.

TODO(agents): Agent base class: identity, rules loading (via modules.vault),
              task queue, report writer.
TODO(agents): implement read-only agents first: Research, Monitoring.
TODO(agents): agent status registry exposed at /api/v1/agents.
TODO(agents): explicit gate — Execution Agent stays a stub until the
              paper-trading track record justifies Stage 5 (see roadmap).
"""
