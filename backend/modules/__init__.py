"""Domain modules — one package per business capability.

Each module owns its domain logic and exposes a small public surface
consumed by services. Modules may import `database`, `models`, `utils`,
`config` — never `api` or `services` (dependency rule points inward).

Current modules (scaffolded, see each package for its TODO plan):
- solana : read-only chain access (RPC client)
- market : market data collection & analysis
- agents : the seven-agent system runtime
- vault  : bridge to the Obsidian knowledge layer
"""
