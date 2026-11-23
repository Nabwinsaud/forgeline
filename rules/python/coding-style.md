# Python coding style

- `ruff check` and `ruff format` clean; `mypy` (or the repo's type checker) passes on changed code.
- Type-annotate every function signature; avoid `Any` outside boundaries.
- Use `X | None`, built-in generics (`list[str]`), and `from __future__ import annotations` where
  the repo does.
- Structured data in dataclasses or pydantic models, not loose dicts.
- Business logic in service modules; routes/views stay thin.
- Validate request data, settings and third-party payloads with pydantic (or the framework's
  forms/serializers) at the boundary.
- Settings from environment via a typed settings object; no secrets in code.
- Define domain exceptions; map them to HTTP responses in one handler.
- Never bare `except:`; never `except Exception: pass`. Re-raise with `raise X from err`.
- No blocking I/O inside `async def`; use async clients or run in a thread.
- Set timeouts on every outbound HTTP call.
- Context managers for files, sessions, locks and transactions.
- No mutable default arguments.
- Use `logging` with module-level `logger = logging.getLogger(__name__)`; no `print` in app code.
- f-strings for messages, never for SQL.
- Use `pathlib` for paths, `datetime` with timezones (UTC) for times, `Decimal` for money.
- Imports at module top, absolute, sorted by the linter; no wildcard imports.
- Keep dependencies declared in `pyproject.toml` with the repo's lock tool.
