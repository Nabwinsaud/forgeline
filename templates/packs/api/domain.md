### API contract (pack: api)

- Never break existing clients: no removing or renaming fields, changing types, or making optional inputs required. Add new fields instead, or version the endpoint.
- Validate every input at the edge: types, ranges, lengths, enums. Reject unknown or invalid input with 400 and a clear message.
- Errors have one shape across the API (e.g. `{"error": {"code", "message"}}`) and the right status code: 400 bad input, 401 not logged in, 403 not allowed, 404 not found, 409 conflict, 422 failed a business rule.
- Lists are paginated with a limit cap. No endpoint returns an unbounded list.
- Writes that clients may retry (create, pay, send) accept an idempotency key.
- Every new or changed endpoint has a test for the happy path and at least one error path, and the API docs (OpenAPI or README) are updated in the same PR.
