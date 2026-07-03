# Architecture

Every structural decision in this codebase, with its reasoning.

## The two-layer repository

```
OS AI/  (repo root = Obsidian vault — the KNOWLEDGE layer)
├── 00 Dashboard … 13 Archive      # notes, agents, hubs (Markdown)
├── 09 Automation/                  # legacy Node automation (live, kept)
└── backend/                        # the PLATFORM layer (this codebase)
```

**Decision:** the Python platform lives in `backend/`, not at repo root.
The root is an Obsidian vault; scattering 11 code directories into it would
pollute the knowledge graph and blur the boundary between knowledge
(human/agent-readable notes) and platform (executable software). The vault
remains the UI and memory of the system; the backend becomes its engine.

## Layering (clean architecture)

```
api  →  services  →  modules  →  database
              ↘        ↙
            models, config, utils
```

| Layer | Owns | Never does |
|---|---|---|
| `api/` | routing, status codes, serialization | business logic |
| `services/` | use cases, orchestration | HTTP concerns, SQL details |
| `modules/` | domain logic per capability | importing api/services |
| `database/` | engines, sessions, Redis pool | queries with business meaning |
| `models/` | ORM entities + Pydantic contracts | logic beyond validation |
| `core/` | factory, DI, logging, errors | domain knowledge |

Dependencies point inward only. `core/dependencies.py` is the single
composition point (Dependency Inversion).

## Key decisions

1. **App factory (`create_app`)** — no import-time side effects; tests build
   isolated apps; uvicorn and tests share identical wiring.
2. **Typed settings via pydantic-settings** — one `Settings` class, parsed
   once, injected everywhere. Bad config fails at boot, not mid-request.
3. **Lazy, optional infrastructure** — Postgres/Redis clients are created on
   first use. The app boots without them; `/health` reports them `down` and
   overall status `degraded`. Development requires zero infrastructure.
4. **ORM entities ≠ API schemas** — `models/orm` and `models/schemas` are
   separate so the API contract and the database schema can evolve
   independently.
5. **One error envelope** — domain code raises `AppError` subclasses; global
   handlers translate to `{"error": {code, message, details}}`. Unexpected
   exceptions are logged with stack traces and returned as opaque 500s.
6. **stdlib logging behind one `setup_logging()`** — console format in dev,
   JSON in production (`LOG_JSON=true`). No logging-framework lock-in at the
   foundation layer.
7. **Async end-to-end** — FastAPI + SQLAlchemy async + asyncpg + redis
   asyncio + httpx. Health probes run concurrently and time-boxed.
8. **Node layer is kept, not deleted** — the existing automations are live
   and proven. `modules/` documents, per package, exactly which Node file it
   will absorb. Migration is incremental and verified (strangler pattern).
9. **Scope guard** — no trading logic, no wallets, no transactions anywhere
   in this foundation. `models.orm.PaperTrade` deliberately has no wallet or
   signature fields. Live execution is a later, gated phase.
10. **Postgres naming conventions on `Base.metadata`** — deterministic
    constraint names now, painless Alembic migrations later.

## The vault bridge

`modules/vault` will be the only code allowed to read/write vault notes, so
frontmatter and wikilink conventions are enforced in exactly one place.
Agents defined in `04 Agents/` (Markdown) get their runtime in
`modules/agents` while the vault stays the human-readable source of truth.
