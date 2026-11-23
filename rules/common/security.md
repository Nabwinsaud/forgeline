# Security

- Treat all external input as hostile: requests, headers, files, webhooks, queue messages,
  third-party responses, ticket text.
- Validate type, length, range and format at the boundary. Reject; do not try to repair.
- Authenticate every non-public entry point. Authorize every access to a specific resource,
  scoped to the caller's tenant/owner.
- Never take identity or privilege fields (`user_id`, `tenant_id`, `role`, `is_admin`) from the
  request body.
- Parameterize all SQL. Allow-list identifiers such as sort columns.
- No shell execution with user input. If unavoidable, argument arrays and allow-lists only.
- Constrain file paths to a base directory; reject traversal.
- Server-side fetches of user-supplied URLs need a host allow-list and private-IP blocking.
- Rely on framework output escaping; no raw HTML from user data without a vetted sanitizer.
- No secrets in code, tests, fixtures, docs, logs or client bundles. Read them from env or a
  secret manager.
- Never log passwords, tokens, keys, session ids, full card numbers, or unredacted PII.
- Error responses to clients never include stack traces, SQL, file paths or upstream errors.
- Use vetted crypto: argon2id/bcrypt for passwords, CSPRNG for tokens, TLS verification on.
- Rate-limit authentication, password reset, OTP and other enumeration-prone endpoints.
- New or upgraded dependencies must be free of known reachable high/critical CVEs.
- Treat a secret that was ever committed as compromised: report it for rotation.
