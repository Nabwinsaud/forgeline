# Per-agent domain notes

Optional. A file named `<agent>.md` here is appended to that agent's brief, after `domain.md`.

Examples:
- `backend-builder.md` — "Use the `apperr` package for errors. Handlers live in `internal/http/`."
- `frontend-builder.md` — "Use `@/components/ui`. Data fetching via TanStack Query hooks in `src/api/`."
- `qa-validator.md` — "Log in as `qa+dev@example.com` (password in env `QA_PASSWORD`)."
- `intake.md` — "Anything touching `billing/` is high risk."

Agent names: intake, spec-writer, backend-builder, frontend-builder, unit-test-engineer,
e2e-test-engineer, security-engineer, code-reviewer, security-reviewer, ux-reviewer, approver, qa-validator.
