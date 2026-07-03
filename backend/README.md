# OS AI — Backend Platform

Production-grade foundation for the AI Operating System: Solana research, market
intelligence, automation, documentation, and AI agents.

**Scope guard:** this foundation contains **no trading logic, no wallet
connections, no blockchain transactions**. Those arrive in later phases behind
explicit gates (see `docs/ROADMAP.md`).

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11, fully typed |
| API | FastAPI (async) |
| Validation / Settings | Pydantic v2 + pydantic-settings |
| Database | PostgreSQL (SQLAlchemy 2.0 async + asyncpg) |
| Cache / Queues | Redis (redis-py asyncio) |
| Containers | Docker + docker-compose |
| Tests | pytest |

## Layout (clean architecture)

```
backend/
├── api/         # HTTP layer — routers only, no business logic
├── config/      # Typed settings loaded from environment / .env
├── core/        # App factory, logging, errors, DI, lifespan
├── database/    # Engine/session/Redis providers (infrastructure)
├── models/      # ORM entities + Pydantic schemas
├── modules/     # Domain modules: solana, market, agents, vault
├── services/    # Application services (use cases)
├── utils/       # Small shared helpers
├── scripts/     # Operational scripts (init_db, dev server)
├── tests/       # Unit tests
└── docs/        # Architecture, roadmap, developer docs
```

Dependency rule: `api → services → modules → database`. Nothing imports upward.

## Quickstart

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env            # then edit as needed
uvicorn main:app --reload         # http://127.0.0.1:8000/api/v1/health
pytest                            # run the test suite
```

The app boots **without** PostgreSQL/Redis (components report `down` in
`/api/v1/health`); start them with `docker compose up -d db redis`.

## Documentation

- `docs/ARCHITECTURE.md` — every architectural decision, explained
- `docs/ROADMAP.md` — phased plan to full system
- `docs/IMPLEMENTATION_NOTES.md` — what exists, TODOs, duplication report
- `docs/DEVELOPER_GUIDE.md` — conventions, how to add a module
