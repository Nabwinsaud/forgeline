---
name: security-review
description: Security review procedure for a diff - walk every entry point from authn/authz through input to dangerous sinks, run an OWASP Top 10 pass, run scanners (gosec, govulncheck, npm audit, pip-audit, semgrep, gitleaks) and grade findings by a fixed severity rubric. Use when reviewing or hardening code that handles input, auth, secrets, files, URLs or dependencies.
---

# Security review

Assume the attacker controls every byte that crosses a trust boundary: HTTP requests, headers,
cookies, query strings, uploaded files, webhook payloads, message queue events, ticket text, and
data from third-party APIs. Your job is to follow that data through the diff and find where it
reaches something that can hurt.

## 1. Entry-point walk

List every entry point the diff adds or changes (route, handler, CLI command, job consumer,
webhook). For each one, answer:

1. **Authentication** - is a valid identity required? Is the check in middleware that actually
   wraps this route? Are public routes intentionally public?
2. **Authorization** - is the caller allowed to act on *this* resource? Look for object-level
   checks: `WHERE id = $1 AND tenant_id = $2`, not just `WHERE id = $1`. Missing ownership checks
   (IDOR) are the most common real bug.
3. **Input validation** - types, ranges, lengths, enums, formats validated at the boundary,
   before use. Reject, do not "clean".
4. **Sinks** - trace each input to where it ends up:

| Sink | Safe pattern |
|---|---|
| SQL | Parameterized queries / sqlc / ORM binds. Never string-concatenate. Identifiers (column for sort) from an allow-list. |
| Shell | Avoid. If needed, exec with an argument array, no shell, fixed binary path, allow-listed args. |
| Filesystem | Resolve and confirm the path stays under a base dir; reject `..`, absolute paths, symlinks out. |
| Outbound HTTP | Allow-list hosts; block private/link-local/metadata IPs after DNS resolution; no redirects to them. |
| HTML | Framework auto-escaping; no `dangerouslySetInnerHTML` / `v-html` / `|safe` with user data unless sanitized with a vetted library. |
| Redirects | Relative paths or allow-listed hosts only. |
| Deserialization | No pickle/yaml.load/gob on untrusted input; strict JSON decoding with size limits. |
| Logs | No secrets, tokens, passwords, full card numbers, or raw PII. |
| Templates / eval | Never evaluate user input as code or template. |

## 2. OWASP Top 10 pass

- **Broken access control** - IDOR, missing role checks, privilege escalation via mass
  assignment (`role`, `is_admin`, `tenant_id` accepted from the body).
- **Cryptographic failures** - plaintext secrets, weak hashing (use bcrypt/argon2id for
  passwords), home-made crypto, `math/rand` / `Math.random` for tokens, TLS verification disabled.
- **Injection** - SQL, command, path, LDAP, header (CRLF), template.
- **Insecure design** - no rate limit on login/OTP/reset, enumeration via different error
  messages, business logic that trusts client-computed totals.
- **Security misconfiguration** - debug mode, verbose errors with stack traces, permissive CORS
  (`*` with credentials), missing security headers, default credentials.
- **Vulnerable components** - new or bumped dependencies with known CVEs.
- **Identification and auth failures** - session fixation, tokens without expiry, JWT `alg`
  not pinned, no signature verification, password reset tokens reusable.
- **Integrity failures** - unsigned webhooks accepted, unpinned CI actions, untrusted deserialization.
- **Logging and monitoring failures** - security events (login failure, permission denied) not
  logged; sensitive data logged.
- **SSRF** - any user-supplied URL fetched server-side (see sink table).

## 3. Web specifics

- **XSS**: React/Vue escape by default; look for raw HTML APIs, `href={userUrl}` without scheme
  check (`javascript:`), and server-rendered templates with unescaped output.
- **CSRF**: cookie-authenticated state-changing endpoints need SameSite=Lax/Strict cookies plus a
  CSRF token or a custom-header check. Token-in-header APIs are not cookie-exposed.
- **Cookies**: `HttpOnly`, `Secure`, `SameSite` on session cookies.
- **CORS**: explicit origin allow-list; never reflect arbitrary `Origin` with credentials.

## 4. Secrets

- No keys, tokens, passwords, connection strings or private certs in code, tests, fixtures,
  migrations, docs or committed `.env` files. Read from environment or a secret manager.
- Frontend bundles are public: nothing secret in `VITE_*` / `NEXT_PUBLIC_*` variables.
- A secret committed even once is compromised: report it as blocking and say it must be rotated.

## 5. Tools

Run what the repo supports; report the command and summary in your result.

```bash
# Go
gosec ./...
govulncheck ./...
# Node
npm audit --omit=dev --audit-level=high
# Python
pip-audit
bandit -r src -q
# Any language
semgrep scan --config auto --error
gitleaks detect --no-banner --redact
```

Scanner output is a lead, not a verdict. Confirm each hit by reading the code; dismiss false
positives with a one-line reason. A vulnerable dependency matters only if it is reachable or
in the runtime path - `govulncheck` tells you this for Go; for others, check the call sites.

## 6. Severity rubric

| Severity | Examples | Status |
|---|---|---|
| `critical` | Auth bypass, SQL/command injection, RCE, committed live secret, cross-tenant data access. | blocking |
| `high` | IDOR on sensitive data, stored XSS, SSRF to internal network, missing authz on write endpoint, reachable high CVE. | blocking |
| `medium` | Reflected XSS needing interaction, missing rate limit on auth, verbose errors leaking internals, PII in logs. | blocking unless domain says otherwise |
| `low` | Missing hardening header, weak but non-exploitable config, unreachable CVE. | non-blocking |

## Finding format

```json
{
  "severity": "high",
  "category": "broken-access-control",
  "file": "internal/invoices/handler.go",
  "line": 42,
  "issue": "GET /invoices/{id} loads by id only; any authenticated user can read another tenant's invoice.",
  "exploit": "Log in as tenant B, request /invoices/<tenant A id> -> 200 with data.",
  "fix": "Use GetInvoiceForTenant(ctx, id, auth.TenantID(ctx)) and return 404 when no row; add a test with two tenants."
}
```

Include an exploit sketch for anything `high` or above. Never run exploits against shared or
deployed environments - reason from code and local tests only.
