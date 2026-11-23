#!/usr/bin/env bash
# Deterministic gate. Runs in the job worktree. Exit 0 = pass. No LLM involved.
# Env: FACTORY_BASE (base branch), FACTORY_AREAS (comma list), FACTORY_JOB.
set -euo pipefail

has_area() { [[ ",${FACTORY_AREAS:-backend,frontend}," == *",$1,"* ]]; }
step() { echo; echo "==> $*"; }

if has_area backend && [ -d backend ]; then
  pushd backend >/dev/null
  step "go: generated code is up to date"
  if [ -f sqlc.yaml ] || [ -f sqlc.yml ]; then sqlc generate; fi
  go generate ./...
  git diff --exit-code -- . || { echo "generated code is stale: run sqlc generate / go generate and commit"; exit 1; }

  step "go: build, vet, test"
  go build ./...
  go vet ./...
  go test -race -count=1 ./...

  if command -v govulncheck >/dev/null; then step "go: govulncheck"; govulncheck ./...; fi
  popd >/dev/null
fi

if has_area frontend && [ -d frontend ]; then
  pushd frontend >/dev/null
  step "frontend: install"
  npm ci --no-audit --no-fund
  step "frontend: typecheck, lint, test, build"
  npx tsc --noEmit
  npm run lint --if-present
  npm test -- --run
  npm run build
  popd >/dev/null
fi

step "secrets"
if command -v gitleaks >/dev/null; then
  gitleaks detect --no-banner --log-opts="${FACTORY_BASE:-main}..HEAD"
fi

echo; echo "gate: all checks passed"
