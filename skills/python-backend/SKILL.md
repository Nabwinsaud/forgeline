---
name: python-backend
description: Framework-agnostic Python service patterns (FastAPI or Django) - strict typing, pydantic validation at the boundary, dependency injection, async correctness, SQLAlchemy and Alembic basics, pytest fixtures and factories, coverage, ruff and mypy. Use when writing or reviewing Python backend code.
---

# Python backend

Match the repo's framework and conventions. These defaults apply where it is silent.

## Layout

```
src/app/
  api/            routers / views: thin, HTTP only
  orders/         service.py, models.py, schemas.py, errors.py, repository.py
  db.py           engine/session factory
  settings.py     typed settings from env
tests/
  conftest.py     fixtures
  factories.py
  orders/test_service.py
```

- Business logic in services, not in routes, models' `save()`, or signals.
- Settings via `pydantic-settings` (or Django settings reading env). Never hard-code secrets.

## Typing

- Type every public function signature. `mypy --strict` (or the repo's config) passes on changed code.
- Prefer `dataclass(frozen=True)` / pydantic models over dicts for structured data.
- `X | None` for optional; no implicit `None` returns from functions typed otherwise.
- Avoid `Any`; if needed, contain it at the edge.

## Validation at the boundary

```python
class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: constr(min_length=1, max_length=64)
    quantity: conint(ge=1, le=1000)
```

- Request bodies, query params, webhook payloads, and third-party responses go through a schema.
- Never accept `tenant_id`, `user_id`, `role` from the body - take them from the auth context.
- Response schemas control output; do not return ORM objects directly.

## Errors

```python
class DomainError(Exception): code = "domain_error"
class NotFound(DomainError): code = "not_found"
class Conflict(DomainError): code = "conflict"
```

Map once in an exception handler: `NotFound -> 404`, `Conflict -> 409`, validation -> 422,
everything else -> 500 with a generic message and a logged traceback. Never bare `except:`;
never `except Exception: pass`. Re-raise with `raise ... from err` to keep the cause.

## Dependency injection

FastAPI: `Depends()` for session, current user, services. Django: pass collaborators into service
functions explicitly. Either way, tests can swap them without monkeypatching module globals.

```python
def get_order_service(session: Session = Depends(get_session)) -> OrderService:
    return OrderService(session, clock=SystemClock())
```

## Async correctness

- In `async def`, never call blocking I/O (requests, sync DB drivers, `time.sleep`, big file
  reads). Use async clients or `await anyio.to_thread.run_sync(...)`.
- Do not mix sync SQLAlchemy sessions into async routes.
- `asyncio.gather` for independent I/O; handle exceptions from every task.
- Set timeouts on every outbound call (`httpx.AsyncClient(timeout=10)`).
- If a route is CPU-bound or uses sync libraries, make it plain `def` so the framework threads it.

## SQLAlchemy / Alembic

- SQLAlchemy 2.0 style: `select(Order).where(Order.tenant_id == tenant, Order.id == id)`.
- One session per request/unit of work; commit in the service or a transaction context, not in
  repositories called in loops.
- Avoid N+1: `selectinload` / `joinedload` for relationships you iterate.
- Raw SQL only via `text()` with bound params. Never f-strings into SQL.
- Schema changes: `alembic revision --autogenerate -m "..."`, then read and fix the draft;
  `upgrade head`, `downgrade -1`, `upgrade head` locally. See `database-migrations`.
- Django: `makemigrations`, review, `migrate`; never edit applied migrations.

## Testing with pytest

```python
@pytest.fixture
def order_service(db_session, fake_clock):
    return OrderService(db_session, clock=fake_clock)

@pytest.mark.parametrize("qty", [0, -1])
def test_create_order_rejects_non_positive_quantity(client, auth_headers, qty):
    r = client.post("/orders", json={"sku": "A", "quantity": qty}, headers=auth_headers)
    assert r.status_code == 422
```

- Fixtures in `conftest.py`, scoped narrowly (`function` by default; `session` only for the DB
  engine / container).
- Real Postgres for repository and integration tests (testcontainers or compose service); wrap
  each test in a transaction rolled back at teardown.
- Factories (`factory_boy` or simple builder functions) for test data; no shared mutable fixtures.
- Fake outbound HTTP with `respx` / `responses`; freeze time with injected clocks or `freezegun`.
- `pytest-asyncio` (or anyio) for async tests; do not call `asyncio.run` inside tests.

## Tooling

```bash
ruff check . && ruff format --check .
mypy src
pytest -q --cov=src --cov-report=term-missing
pip-audit
```

All must pass before returning `pass`. Fix the code, not the config - do not add ignores or lower
the coverage threshold to get green.

## Logging

- `logging` with structured output (JSON) configured once at startup; `logger = logging.getLogger(__name__)`.
- Include request id; never log passwords, tokens, or full PII payloads.
- `logger.exception` inside `except` to keep the traceback.
