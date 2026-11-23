---
name: go-backend
description: Idiomatic Go service code for factory jobs - package layout, context propagation, error wrapping and typed domain errors mapped to HTTP, thin handlers, sqlc + pgx with transactions, slog logging, and testing with table-driven tests, httptest, testcontainers and the race detector. Use when writing or reviewing Go backend code.
---

# Go backend

Match the repo first. These defaults apply where the repo is silent.

## Layout

```
cmd/api/main.go            wiring only: config, logger, pool, router, server
internal/
  http/                    handlers, middleware, request/response DTOs, error mapping
  orders/                  domain package: service, domain types, errors
  store/ or db/            sqlc output + thin store helpers
  platform/                config, logging, clock, ids
db/migrations/  db/queries/
```

- Package by domain (`orders`, `billing`), not by layer-only names like `models` / `utils`.
- `internal/` for everything not meant to be imported by other modules.
- Define interfaces where they are consumed, small (1-3 methods), only when a test or a second
  implementation needs them.
- No package-level mutable state. Dependencies are passed into constructors.

## Context

- First parameter of anything that does I/O: `ctx context.Context`.
- Use the request context (`r.Context()`); never `context.Background()` inside a request path.
- Respect cancellation in loops: `select { case <-ctx.Done(): return ctx.Err() ... }`.
- Context values only for request-scoped data (request id, auth identity), via typed keys.

## Errors

```go
var ErrNotFound = errors.New("not found")

type ValidationError struct{ Field, Msg string }
func (e *ValidationError) Error() string { return e.Field + ": " + e.Msg }

func (s *Service) Get(ctx context.Context, tenant, id string) (Order, error) {
    row, err := s.q.GetOrder(ctx, db.GetOrderParams{ID: id, TenantID: tenant})
    if errors.Is(err, pgx.ErrNoRows) {
        return Order{}, ErrNotFound
    }
    if err != nil {
        return Order{}, fmt.Errorf("get order %s: %w", id, err)
    }
    return toOrder(row), nil
}
```

- Wrap with `%w` and context about *what* was being done. Do not log and return the same error.
- Check with `errors.Is` / `errors.As`, never string comparison.
- Domain errors are defined in the domain package; the HTTP layer maps them once:

```go
func writeError(w http.ResponseWriter, r *http.Request, err error) {
    var ve *orders.ValidationError
    switch {
    case errors.As(err, &ve):
        writeJSON(w, 422, errBody("validation_failed", ve.Error()))
    case errors.Is(err, orders.ErrNotFound):
        writeJSON(w, 404, errBody("not_found", "Order not found."))
    case errors.Is(err, orders.ErrConflict):
        writeJSON(w, 409, errBody("conflict", "Order already exists."))
    default:
        slog.ErrorContext(r.Context(), "unhandled error", "err", err)
        writeJSON(w, 500, errBody("internal", "Something went wrong."))
    }
}
```

- No `panic` for expected failures. Recover middleware only as a last line.

## Handlers stay thin

Decode -> validate -> call service -> map result/error -> encode. No SQL, no business rules.

```go
func (h *Handler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    var req createOrderRequest
    dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20))
    dec.DisallowUnknownFields()
    if err := dec.Decode(&req); err != nil {
        writeJSON(w, 400, errBody("bad_request", "Invalid JSON."))
        return
    }
    if err := req.validate(); err != nil { writeError(w, r, err); return }
    o, err := h.svc.Create(r.Context(), auth.Tenant(r.Context()), req.toInput())
    if err != nil { writeError(w, r, err); return }
    writeJSON(w, 201, toResponse(o))
}
```

## sqlc + pgx

- Use `pgxpool.Pool`; sqlc with `sql_package: pgx/v5`.
- Queries live in `.sql` files; run `sqlc generate`; never edit generated code
  (see `database-migrations`).
- Tenant/ownership predicates belong in the SQL.

Transactions:

```go
func (s *Service) Place(ctx context.Context, in PlaceInput) (err error) {
    tx, err := s.pool.Begin(ctx)
    if err != nil { return fmt.Errorf("begin: %w", err) }
    defer func() {
        if err != nil { _ = tx.Rollback(ctx) }
    }()
    q := s.q.WithTx(tx)
    if err = q.ReserveStock(ctx, ...); err != nil { return fmt.Errorf("reserve: %w", err) }
    if err = q.InsertOrder(ctx, ...); err != nil { return fmt.Errorf("insert: %w", err) }
    return tx.Commit(ctx)
}
```

Use DB constraints (unique, FK, check) for invariants; map constraint violations
(`pgconn.PgError.Code == "23505"`) to domain conflict errors.

## Logging

- `log/slog` with JSON handler; pass ctx (`slog.InfoContext`) so request id is attached.
- Structured keys, not formatted strings: `slog.Info("order placed", "order_id", id)`.
- Never log secrets, tokens, passwords, or full request bodies with PII.

## Concurrency

- Every goroutine has an owner and an exit path; use `errgroup.WithContext` for fan-out.
- Protect shared maps with a mutex or avoid sharing. Channels for ownership transfer, not as locks.
- Always run tests with `-race`.

## Testing

Table-driven with subtests:

```go
func TestValidateQuantity(t *testing.T) {
    tests := []struct{ name string; qty int; wantErr bool }{
        {"one is ok", 1, false},
        {"zero rejected", 0, true},
        {"negative rejected", -3, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := validateQuantity(tt.qty)
            if (err != nil) != tt.wantErr { t.Fatalf("err = %v, wantErr %v", err, tt.wantErr) }
        })
    }
}
```

Handlers with `httptest`:

```go
rec := httptest.NewRecorder()
req := httptest.NewRequest(http.MethodPost, "/orders", strings.NewReader(`{"sku":"A","quantity":0}`))
router.ServeHTTP(rec, req)
if rec.Code != 422 { t.Fatalf("status = %d, body = %s", rec.Code, rec.Body) }
```

- Store/service tests run against real Postgres via testcontainers-go (or the compose DB the
  domain provides), with migrations applied in `TestMain`.
- `t.Helper()` in helpers, `t.Cleanup` for teardown, `t.Parallel()` when isolated.
- Commands: `go test -race -count=1 ./...`, `go vet ./...`, `go generate ./...` then
  `git status --porcelain` to prove generated code is fresh.
