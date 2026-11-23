---
name: code-review-checklist
description: Review procedure for factory PRs - the order to read in, what to check (spec correctness, tests, errors, concurrency, data, design, domain rules), severity levels and how to write a finding with a concrete fix. Use when reviewing a diff or PR as a read-only reviewer agent.
---

# Code review checklist

You are read-only. You did not write this code. Your output decides whether the job goes back to
build (`changes_requested`) or forward (`pass`). False positives cost a full rebuild attempt;
false negatives ship bugs. Be precise.

## Read in this order

1. **Spec** - goal, acceptance criteria, out of scope, risk.
2. **Domain harness** - `.factory/domain.md` rules and invariants. Violations are blocking.
3. **Diff vs base** - `git diff <base>...HEAD --stat`, then the full diff.
4. **Surrounding code** - callers of changed functions, sibling handlers, existing patterns.
5. **Tests** - read them as carefully as production code.

Run the tests if you can. A claim like "this panics on nil" is stronger when you have checked it.

## Checklist (in priority order)

### 1. Correctness against the spec
- Every AC implemented? Map AC -> code -> test. A missing AC is blocking.
- Edge cases from the spec handled: empty, zero, max, duplicate, not found, forbidden.
- Off-by-one in loops, pagination, date ranges (inclusive/exclusive, timezone).
- Nil / undefined / None dereferences on optional fields.
- Spec drift: features, endpoints, config or UI not requested. Major unless harmless.

### 2. Tests prove the criteria
- Would the test fail if the production change were reverted or broken?
- Assertions on outcomes, not on mocks being called.
- Unhappy paths tested, not just the happy path.
- Data access tested against a real DB, not a mocked query layer.
- No skipped, focused or weakened tests; no deleted tests without reason.

### 3. Error handling
- Every error checked, wrapped with context, or deliberately handled. None swallowed.
- Errors mapped to correct status codes / user messages; internals not leaked to clients.
- Cleanup on failure: transactions rolled back, files closed, partial state not left behind.

### 4. Concurrency and resources
- Shared state guarded; no data races (goroutines, async tasks, React state updates after unmount).
- Context / cancellation propagated; no goroutine or task leaks.
- Check-then-act races on uniqueness or balances (use constraints or row locks).
- Unbounded loops, queries or memory on user-controlled input.

### 5. Data
- Migrations: new file, reversible, safe on a large table, no edit of applied migrations.
- Queries parameterized; N+1 queries in loops; missing indexes for new filters.
- Transactions around multi-statement writes that must be atomic.
- Generated code regenerated, not hand-edited.

### 6. Design
- Fits existing patterns in this repo; no parallel second way of doing the same thing.
- No speculative abstraction (interfaces with one impl and no test need, config nobody sets).
- Names say what things are. Functions do one thing. Handlers thin.

### 7. Domain rules
- Business invariants from the domain harness hold (money rounding, tenancy isolation, audit
  logging, state machine transitions).

Security issues go to the security reviewer, but if you see one, report it as blocking anyway.

## Severity

| Level | Meaning | Effect |
|---|---|---|
| `blocking` | Wrong behavior, missing AC, data loss risk, security hole, domain rule broken, tests that do not prove the criteria. | `changes_requested` |
| `major` | Real defect or maintainability problem that will bite soon: unhandled edge case outside the ACs, N+1, confusing design, spec drift. | `changes_requested` if more than trivial to fix; otherwise note it. |
| `nit` | Small readability improvement. Optional. | Does not block. |

If there is no `blocking` finding, return `pass`.

## Writing a finding

Each finding: where, what is wrong, why it matters, exactly how to fix it.

```json
{
  "severity": "blocking",
  "file": "internal/orders/handler.go",
  "line": 88,
  "issue": "Quantity is parsed but never checked; quantity=0 creates an order with total 0 (violates AC4).",
  "fix": "Return 422 invalid_quantity when qty < 1 before calling svc.Create; add a table case for 0 and -1 in TestCreateOrderHandler."
}
```

Bad finding: `"issue": "Validation could be better"`. The builder cannot act on it.

- One issue per finding. Point at a line.
- The fix is concrete enough to implement without asking you.
- If you are unsure, say what you checked and what would confirm it - and use `major`, not
  `blocking`.

## What NOT to flag

- Formatting, import order, quote style - linters own these.
- Personal preference between two valid idioms already used in the repo.
- Missing features that are in "Out of scope".
- Refactors of code the diff did not touch, unless the change makes it actively wrong.
- Hypothetical scale problems with no basis in the spec or domain.
- Test style when the tests are correct and readable.

## Output

Return `pass` or `changes_requested` with the `findings` array. Keep `nit`s few - three good
findings beat fifteen mixed ones.
