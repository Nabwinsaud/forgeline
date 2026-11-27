### Access control (pack: auth)

- Every endpoint and action checks two things: who the user is (authentication) and whether they may do this to this record (authorization). Hiding a button is not authorization.
- Records that belong to a user, team or tenant are always queried with that owner in the filter. Never load by id alone.
- Deny by default. A new route, role or permission starts closed.
- Passwords are hashed with a slow algorithm (argon2, bcrypt, scrypt). Tokens and secrets are never logged, never in URLs, never in the repo.
- Sessions and tokens expire, and logout or a password change revokes them.
- TLS verification is never turned off, not even "just for this call".
- Changes to login, roles, permissions, sessions or tenant filters are high risk and need a human to merge.
