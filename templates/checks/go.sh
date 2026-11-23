
# --- Go: __DIR__ ---------------------------------------------------------------
if has_area __AREA__; then
  pushd "__DIR__" >/dev/null
  step "go (__DIR__): generated code is fresh"
  if [ -f sqlc.yaml ] || [ -f sqlc.yml ] || [ -f sqlc.json ]; then sqlc generate; have sqlc && sqlc vet || true; fi
  go generate ./...
  git diff --exit-code -- . || { echo "stale generated code: run sqlc generate / go generate and commit"; exit 1; }
  step "go (__DIR__): build · vet · test"
  test -z "$(gofmt -l . | grep -v '^vendor/' || true)" || { echo "gofmt needed:"; gofmt -l .; exit 1; }
  go build ./...
  go vet ./...
  go test -race -count=1 ./...
  if have staticcheck; then step "go: staticcheck"; staticcheck ./...; fi
  if have govulncheck; then step "go: govulncheck"; govulncheck ./...; fi
  popd >/dev/null
fi
