# OS AI — AI Operating System

A two-layer system for Solana research, market intelligence, automation,
documentation, and AI agents.

| Layer | Where | What |
|---|---|---|
| 🧠 **Knowledge** | repo root (Obsidian vault) | Dashboards, 7 agents, Solana knowledge base, strategies, memory — start at `00 Dashboard/Home.md` |
| ⚙️ **Platform** | [`backend/`](backend/README.md) | Python/FastAPI/PostgreSQL/Redis foundation — clean architecture, typed, tested |
| 🤖 **Automation (legacy)** | `09 Automation/` | Live Node.js pipelines (market data, risk engine, paper scalper) — being absorbed into `backend/modules/` per the [roadmap](backend/docs/ROADMAP.md) |

## Ground rules

- **No live trading, no wallets, no private keys** anywhere in this repo.
  Paper trading only, until the roadmap's Stage 5 gate is explicitly opened.
- The vault is the human-readable source of truth; the platform is its engine.
- Nothing gets deleted during migration — the Node layer runs until the
  Python port reaches proven parity.

## Start here

- Knowledge layer: open the repo in Obsidian → `Home`
- Platform: [`backend/README.md`](backend/README.md)
- Architecture decisions: [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md)
- Roadmap: [`backend/docs/ROADMAP.md`](backend/docs/ROADMAP.md)
