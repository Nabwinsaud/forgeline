---
name: api-design
description: Conventions for HTTP/JSON APIs built by the factory - resource paths, methods, status codes, one error body shape, cursor pagination, filtering, idempotency keys, versioning, boundary validation and backward-compatibility rules. Use when adding or changing an endpoint, or reviewing an API contract in a spec or PR.
---

# API design

Consistency beats cleverness. Before inventing anything, read two or three existing endpoints in
the repo and match them. These rules apply where the repo has no established convention.

## Resources and paths

- Plural nouns, lowercase, kebab-case: `/orders`, `/orders/{id}`, `/orders/{id}/line-items`.
- No verbs in paths for CRUD. For true actions that are not CRUD, use a sub-resource:
  `POST /orders/{id}/cancel`, `POST /invoices/{id}/send`.
- Nest at most one level. Beyond that, filter: `/line-items?order_id=...`.
- IDs are opaque strings to clients (UUID / ULID). Never expose sequential IDs if enumeration matters.
- JSON field names: pick the repo's case (`snake_case` or `camelCase`) and never mix.

## Methods

| Method | Use | Idempotent |
|---|---|---|
| GET | read; no side effects | yes |
| POST | create, or action | no (make it so with idempotency keys) |
| PUT | full replace | yes |
| PATCH | partial update (only fields sent) | should be |
| DELETE | remove | yes (second call -> 404 or 204, be consistent) |

## Status codes

| Code | When |
|---|---|
| 200 | OK with body |
| 201 | Created; include `Location` header and the resource |
| 202 | Accepted for async processing; return a job/status link |
| 204 | Success, no body |
| 400 | Malformed request (bad JSON, wrong types) |
| 401 | Not authenticated |
| 403 | Authenticated but not allowed |
| 404 | Not found - also use for resources the caller may not know exist (avoid leaking existence) |
| 409 | Conflict: duplicate, version mismatch, invalid state transition |
| 412 | `If-Match` precondition failed |
| 422 | Well-formed but fails validation / business rules |
| 429 | Rate limited; include `Retry-After` |
| 500 | Unexpected server error; never leak internals |
| 503 | Dependency down / maintenance |

## Error body

One shape everywhere:

```json
{
  "error": {
    "code": "invalid_quantity",
    "message": "Quantity must be at least 1.",
    "details": [{"field": "items[0].quantity", "issue": "must be >= 1"}],
    "request_id": "01HZX..."
  }
}
```

- `code` is stable, machine-readable, documented. Clients branch on it, not on `message`.
- `message` is safe to show a user. No stack traces, SQL, file paths, or upstream errors.
- `details` lists field-level validation failures.

## Pagination

Prefer cursor pagination for anything that grows:

```
GET /orders?limit=50&cursor=eyJpZCI6...
200 { "data": [...], "next_cursor": "eyJpZCI6...", "has_more": true }
```

- Default and maximum `limit` (e.g. 50 / 200). Clamp, do not error, unless the repo errors.
- Cursor is opaque (base64 of the sort key + id). Order must be stable: always tie-break on id.
- Offset pagination only for small, bounded admin lists.

## Filtering and sorting

- Filters as query params named after fields: `?status=open&customer_id=...`.
- Ranges: `created_after`, `created_before` (ISO 8601, UTC).
- Sorting: `?sort=-created_at` with an allow-list of sortable fields. Never pass a raw param into
  `ORDER BY`.
- Unknown filter params: ignore or 400 - follow existing behavior.

## Idempotency

For POSTs that create money movements, orders, messages or anything a retry must not duplicate:

- Accept `Idempotency-Key` header (client-generated UUID).
- Store key + request hash + response for a window (e.g. 24h), scoped to the caller.
- Same key + same body -> return the stored response. Same key + different body -> 422/409.
- Enforce with a unique constraint, not a read-then-write check.

## Concurrency control

For updates that can collide, return an `ETag` (or `version` field) and require `If-Match` /
`version` on PUT/PATCH. Mismatch -> 412 or 409.

## Validation at the boundary

- Decode strictly: reject unknown fields if the repo does, enforce max body size.
- Validate types, required fields, lengths, ranges, enums, formats in the handler/schema layer.
- Never trust client-provided ownership or role fields (`tenant_id`, `user_id`, `is_admin`) -
  derive them from the authenticated identity.
- Domain rules (stock, state transitions) live in the service layer and map to 409/422.

## Versioning

- Follow the repo's scheme; default is a path prefix `/v1`.
- Additive changes do not need a new version. Breaking changes do, or must be avoided.

## Backward compatibility

Safe (additive):
- New endpoint; new optional request field; new response field; new enum value *only if* clients
  are documented to tolerate unknown values.

Breaking (needs a new version or a coordinated migration, and `high` risk in the spec):
- Removing or renaming a field or endpoint.
- Changing a field's type, format, or meaning.
- Making an optional request field required.
- Changing status codes or error codes clients rely on.
- Tightening validation on existing inputs.
- Changing default sort or pagination behavior.

Deprecate first: keep the old field, add the new one, document, remove in a later release.

## Checklist for a new endpoint

- [ ] Path, method and status codes follow the tables above and the repo.
- [ ] Authn required; authz checks the specific resource.
- [ ] Request validated; error body uses the standard shape and stable codes.
- [ ] List endpoints paginated with a max limit.
- [ ] Unsafe POSTs support idempotency where duplicates hurt.
- [ ] Tests cover success, validation error, 401, 403/404, conflict.
- [ ] OpenAPI / API docs and generated clients updated, if the repo has them.
