# Go coding style

- `gofmt`/`goimports` clean; `go vet ./...` and the repo's `golangci-lint` config pass.
- Package by domain under `internal/`; no `utils`, `common`, `models` grab-bag packages.
- Package names short, lowercase, singular, no underscores; avoid stutter (`orders.Service`, not
  `orders.OrderService`).
- `cmd/<app>/main.go` only wires dependencies; no business logic.
- Pass dependencies into constructors. No package-level mutable state, no `init()` side effects.
- Accept interfaces, return concrete types. Define small interfaces where they are used.
- `ctx context.Context` is the first parameter of any function doing I/O; never store it in a struct.
- Use the request context in request paths, never `context.Background()`.
- Return errors, do not panic, for expected failures.
- Wrap errors with `fmt.Errorf("doing x: %w", err)`; check with `errors.Is` / `errors.As`.
- Do not both log and return an error; handle it once.
- Sentinel or typed domain errors in the domain package; map them to HTTP in one place.
- Handlers are thin: decode, validate, call service, map result.
- Every goroutine has an owner, a cancellation path and an exit; prefer `errgroup`.
- Guard shared state with a mutex or do not share it.
- Close what you open (`defer rows.Close()`, `defer resp.Body.Close()`).
- Set timeouts on HTTP clients and servers; never use `http.DefaultClient` for outbound calls.
- Use `log/slog` with structured keys and the request context.
- Zero values should be useful; avoid constructors that only set defaults the zero value has.
- Keep exported API minimal; unexport anything not used outside the package.
