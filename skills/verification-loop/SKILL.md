---
name: verification-loop
description: The checks an agent runs before reporting a job stage as done - build, typecheck, lint, tests, coverage of changed code, codegen freshness and a self-review of the diff - plus the report format. Use when finishing any build, test or fix stage, before returning pass.
---

# Verification loop

"Done" means the deterministic gate (`.factory/checks.sh`) will pass on your commit and a
skeptical reviewer will not find an obvious miss. Run this loop before returning `pass`. If any
step fails, fix and restart the loop from step 1. Never report success from memory - report what
you just ran.

## 0. Find the project's commands

Prefer, in order:
1. Commands listed in the domain harness (`.factory/domain.md`, agent notes, `.factory/checks.sh`).
2. `Makefile` / `justfile` / `package.json` scripts / `pyproject.toml` tool config.
3. The language defaults below.

You may *read* `.factory/checks.sh` and run it. You may not edit it.

## 1. Build

| Stack | Command |
|---|---|
| Go | `go build ./...` |
| TypeScript | `npm run build` (or `pnpm build`, `vite build`) |
| Python | `python -m compileall -q src` or the package build |

## 2. Typecheck / vet

| Stack | Command |
|---|---|
| Go | `go vet ./...` |
| TypeScript | `npx tsc --noEmit` |
| Python | `mypy src` (or `pyright`) |

## 3. Lint and format

| Stack | Command |
|---|---|
| Go | `gofmt -l .` must print nothing; `golangci-lint run` if configured |
| TypeScript | `npx eslint .` and `npx prettier --check .` |
| Python | `ruff check .` and `ruff format --check .` |

Fix lint findings in code you touched. Do not add blanket disable comments; a targeted
suppression needs a one-line reason.

## 4. Tests

Run the **whole** suite, not only the tests you wrote.

```bash
go test -race -count=1 ./...
npx vitest run
pytest -q
```

Any failure - including one that "was already failing" - must be explained. If a test was
broken on the base branch, verify that by running it on base, and say so in `notes`. Do not
skip or delete it.

## 5. Coverage of changed code

Global percentages hide gaps. Check the files you changed:

```bash
go test -coverprofile=cover.out ./... && go tool cover -func=cover.out | grep -E 'orders|inventory'
npx vitest run --coverage
pytest --cov=src --cov-report=term-missing
```

Every new branch of logic (especially error paths) should be hit. Uncovered changed lines need
either a test or a reason in `notes`.

## 6. Codegen freshness

If the repo generates code (sqlc, protobuf, OpenAPI clients, mocks, `go generate`), regenerate
and confirm nothing changed:

```bash
sqlc generate && go generate ./... && git status --porcelain
npm run codegen && git diff --exit-code
```

A dirty tree after regeneration means you hand-edited generated output or forgot to commit it.

## 7. Secrets and junk

```bash
gitleaks detect --no-banner --redact     # if installed
git status --porcelain                    # nothing untracked that should be ignored
```

No `.env`, credentials, coverage files, build output, editor folders or large binaries in the diff.

## 8. Self-review the diff

```bash
git diff <base>...HEAD --stat
git diff <base>...HEAD
```

Read it as the code reviewer would:
- Does each acceptance criterion have code **and** a test? Map them explicitly.
- Anything built that the spec did not ask for? Remove it.
- Debug prints, commented-out code, stray TODOs, leftover `.only` / `t.Skip`?
- Error paths: is every error returned, wrapped or handled - none swallowed?
- New input reaching SQL, shell, filesystem, URLs or HTML without validation?
- Names and structure consistent with neighbouring code?

## 9. Commit state

```bash
git status --porcelain   # must be empty
git log --oneline <base>..HEAD
```

The gate refuses uncommitted changes. Never push, never merge - the factory does that.

## Report format

Return the stage's `data` block with facts, not adjectives:

```json
{
  "files_changed": ["internal/orders/service.go", "internal/orders/service_test.go"],
  "tests_added": ["TestCreateOrder_RejectsOutOfStock"],
  "commands_run": [
    "go build ./... (ok)",
    "go vet ./... (ok)",
    "go test -race ./... (ok, 214 tests)",
    "sqlc generate && git status --porcelain (clean)"
  ],
  "criteria": {"AC1": "TestCreateOrder_Happy", "AC2": "TestCreateOrder_RejectsOutOfStock"},
  "notes": "Pre-existing flaky test TestWebhookRetry also fails on base; untouched."
}
```

## Status rules

- `pass` only if steps 1-9 all succeeded on the current HEAD.
- `fail` if you could not get the suite green within this attempt - include the failing output
  so the next attempt's brief carries it.
- `needs_human` if the environment is broken (toolchain missing, DB will not start) and it is not
  something your change caused.
