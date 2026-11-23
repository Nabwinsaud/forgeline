# TypeScript testing

- Unit and component tests with Vitest (or the repo's runner); e2e with Playwright.
- Component tests use React Testing Library and test what the user sees and does.
- Query by role, then label, then text; `data-testid` only as a last resort.
- Use `userEvent` over `fireEvent`; use `findBy*` / `waitFor` for async, never fixed timeouts.
- Mock the network at the boundary with MSW; do not mock your own components or hooks.
- Cover loading, empty, error and success states for data-driven components.
- Assert on visible outcomes, not on component state, props, or call counts of internals.
- No snapshot tests as the sole proof of a behavior.
- Reset handlers, timers and mocks between tests (`afterEach`).
- Use fake timers only when testing time-based logic, and restore them.
- Every test is independent; no shared mutable fixtures.
- No `.only` or `.skip` in committed code.
- Type-check test files too; no `any` in tests.
- E2E tests: one journey per acceptance criterion, role/label selectors, no `waitForTimeout`,
  `baseURL` from env, own test data per test.
- Run `vitest run`, `tsc --noEmit`, lint, and the build before finishing.
- Check coverage of changed files with `vitest run --coverage`.
- Test fixtures use obviously fake data; never real customer records or credentials.
