# Developer Guide

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate               # Windows
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
```

## Daily commands

| Task | Command |
|---|---|
| Run dev server | `uvicorn main:app --reload` (or `scripts\dev.bat`) |
| Run tests | `pytest` |
| Start infra | `docker compose up -d db redis` |
| Create tables | `python -m scripts.init_db` |
| API docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/v1/health |

## Conventions (enforced by review)

- **Typing:** every function signature fully typed; no bare `dict` returns
  from services — define a schema.
- **Docstrings:** every module and public function states its purpose.
- **Errors:** raise `core.exceptions.AppError` subclasses in domain code;
  never `HTTPException` outside `api/`.
- **Time:** always `utils.time.utc_now()`; naive datetimes are banned.
- **Imports point inward:** `api → services → modules → database`. A module
  importing from `services/` or `api/` is an architecture violation.
- **TODOs:** `TODO(scope): description` — greppable, scoped, no bare TODO.

## How to add a new capability (example: market snapshots)

1. Domain logic → `modules/market/` (pure, typed, unit-testable)
2. Persistence → entity in `models/orm/`, session via DI
3. Use case → `services/market.py` orchestrating module + repo
4. Contract → response models in `models/schemas/`
5. Endpoint → router in `api/v1/market.py`, include in `api/router.py`
6. Provider → add to `core/dependencies.py`
7. Tests → `tests/test_market.py` (service with fakes, endpoint via client)

Nothing else changes — that is the Open/Closed principle working.

## Testing philosophy

- Tests must pass with **no infrastructure running** (CI-friendly).
- Integration tests that need Postgres/Redis get a `@pytest.mark.integration`
  marker (introduced in Phase 1) and run against docker-compose.
