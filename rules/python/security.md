# Python security

- Run `pip-audit` and `bandit -r src`; fix or justify findings in changed code.
- SQL through the ORM or `text()` with bound parameters; never f-strings or `%` formatting
  into SQL.
- Allow-list column names for dynamic sorting and filtering.
- No `subprocess` with `shell=True` on user input; pass argument lists.
- Never `eval`, `exec`, `pickle.loads`, `marshal`, or `yaml.load` (use `yaml.safe_load`) on
  untrusted data.
- File paths from input: resolve with `Path.resolve()` and confirm `is_relative_to(base)`.
- Outbound requests to user-supplied URLs: host allow-list, block private/loopback/link-local
  addresses after resolution, disable redirects or re-check each hop, set timeouts.
- Validate all request input with pydantic/serializers; `extra="forbid"` where the repo does.
- Never accept `user_id`, `tenant_id`, or role fields from request bodies.
- Scope every query by the authenticated tenant/owner.
- Passwords with argon2 or bcrypt (or Django's hashers); tokens from `secrets`, never `random`.
- Keep `DEBUG` off outside local; never return tracebacks to clients.
- Django: keep CSRF middleware on; use the ORM and template auto-escaping; no `mark_safe` on
  user data.
- Do not disable TLS verification (`verify=False`) outside tests.
- Never log secrets, tokens, `Authorization` headers, or raw PII.
- Secrets come from env or a secret manager via settings; none in code, fixtures, or migrations.
