# Go security

- Run `gosec ./...` and `govulncheck ./...`; fix or justify every finding in changed code.
- SQL only through sqlc or parameterized `pgx` calls; never `fmt.Sprintf` into a query.
- Sort/column names from user input go through an allow-list map.
- `exec.Command` with a fixed binary and argument slice; never `sh -c` with user input.
- File paths from input: `filepath.Clean`, join to a base, then verify the result has the base
  prefix; reject absolute paths and `..`.
- Limit request bodies with `http.MaxBytesReader`; decode JSON with `DisallowUnknownFields` where
  the repo does.
- Set `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout` on `http.Server`.
- Outbound clients have timeouts; user-supplied URLs are checked against an allow-list and
  private/loopback/link-local IPs are blocked after resolution.
- Use `crypto/rand` for tokens and ids; never `math/rand` for anything security-relevant.
- Passwords with `bcrypt` or `argon2id`; compare secrets with `subtle.ConstantTimeCompare`.
- Never set `InsecureSkipVerify: true` outside tests.
- `html/template` for HTML, never `text/template`.
- JWT: pin the algorithm, verify signature, expiry, issuer and audience.
- Authz checks include tenant/owner in the query (`WHERE id = $1 AND tenant_id = $2`).
- Do not log secrets, tokens, `Authorization` headers or raw request bodies with PII.
- Map internal errors to generic 500 responses; never return `err.Error()` to clients.
- Secrets come from env or a secret manager via config; none in code or test fixtures.
