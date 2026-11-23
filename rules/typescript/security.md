# TypeScript security

- Run `npm audit --omit=dev --audit-level=high` (or the pnpm/yarn equivalent); fix or justify
  reachable high/critical findings.
- Client bundles are public: no secrets in `VITE_*`, `NEXT_PUBLIC_*`, or hard-coded constants.
- Never render untrusted HTML; if unavoidable, sanitize with DOMPurify.
- Validate URLs before using them in `href`/`src`/`window.location`; allow only `http(s):` and
  known hosts for redirects.
- Do not build HTML, SQL, shell commands or file paths with string concatenation of user input.
- Node services: parameterized queries or the ORM's bound params; no `eval`, `new Function`,
  or `child_process.exec` with user input (use `execFile` with argument arrays).
- Prefer httpOnly, Secure, SameSite cookies for session tokens over `localStorage`.
- Cookie-authenticated state changes need CSRF protection.
- CORS: explicit origin allow-list; never reflect any origin with credentials.
- Validate every API response and request body with a schema at the boundary.
- Guard against prototype pollution: no deep-merge of untrusted objects into plain objects;
  reject `__proto__`/`constructor` keys.
- Use `crypto.randomUUID()` / `crypto.getRandomValues()` for ids and tokens, never `Math.random`.
- Never log tokens, passwords, or PII to the console or analytics.
- Lock dependency versions with the lockfile; review new dependencies before adding.
- Do not disable TLS verification (`NODE_TLS_REJECT_UNAUTHORIZED=0`) outside local tests.
- Set security headers (CSP, `X-Content-Type-Options`, `Referrer-Policy`) where the app serves HTML.
