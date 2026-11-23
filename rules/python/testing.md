# Python testing

- Use pytest. Tests mirror the package layout under `tests/`.
- Name tests `test_<unit>_<behavior>_<condition>`.
- Shared fixtures in `conftest.py`; default to function scope, widen only for expensive
  resources like a DB container.
- Use `@pytest.mark.parametrize` for input variations of one behavior.
- Build test data with factories (factory_boy or builder functions), not large shared fixtures.
- Repository and integration tests use real Postgres (testcontainers or the compose DB), each
  test in a rolled-back transaction or a truncated schema.
- Do not mock the ORM or your own repositories in data-access tests.
- Fake outbound HTTP with `respx`/`responses`; inject clocks or use `freezegun`.
- Async tests with `pytest-asyncio` or anyio; never `asyncio.run` inside a test.
- API tests go through the framework test client and assert status code and body.
- Cover error paths: validation failures, not found, forbidden, conflicts.
- No `time.sleep` in tests; no network to the internet.
- No `@pytest.mark.skip`/`xfail` to hide failures; `xfail` needs a reason and ticket.
- Run `pytest -q --cov=src --cov-report=term-missing`; changed lines are covered.
- Do not lower `fail_under` or add coverage pragmas to pass.
- Tests type-check and lint like production code.
