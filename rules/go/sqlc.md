# sqlc

- SQL is the source of truth; generated Go is output. Never hand-edit generated files
  (`*.sql.go`, `models.go`, `db.go`, `querier.go`).
- Queries live in the configured `queries` directory as `.sql` files with
  `-- name: QueryName :one|:many|:exec|:execrows|:batchexec` annotations.
- Schema comes from the migrations directory; change schema only through a new migration.
- After changing SQL, schema, or `sqlc.yaml`: run `sqlc generate`, then `go build ./...`.
- Run `sqlc vet` when the repo configures it; fix findings in the SQL.
- Commit generated code in the same commit as the SQL change that produced it.
- After regeneration, `git status --porcelain` must show no unexpected changes; the gate checks
  codegen freshness.
- Use `sqlc.arg(name)` / `sqlc.narg(name)` for readable, nullable parameters.
- Put tenant/ownership filters in the query, not in Go after loading rows.
- Always `ORDER BY` with a unique tie-breaker for lists and pagination.
- Use `LIMIT` on every list query; never return an unbounded result set to a handler.
- Map `pgx.ErrNoRows` to a domain not-found error at the store/service boundary.
- Map constraint violations (`23505` unique, `23503` FK) to domain conflict errors.
- Use `Queries.WithTx(tx)` for multi-statement atomic writes.
- Type overrides (UUID, decimal, timestamps) belong in `sqlc.yaml`, not in wrapper hacks.
- Test queries against real Postgres with migrations applied.
