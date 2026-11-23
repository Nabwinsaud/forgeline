---
name: tdd-workflow
description: Test-first build loop for factory jobs - red, green, refactor, one acceptance criterion at a time, with a commit after each green step. Use when implementing a spec, fixing a bug, or changing behavior inside a job worktree.
---

# TDD workflow

You are building inside a job worktree. The spec's acceptance criteria (AC1, AC2, ...) are your
backlog. Each criterion becomes one or more failing tests before it becomes code. The gate and the
reviewers will check that your tests actually prove the criteria, so write them first and write
them honestly.

## The loop (per acceptance criterion)

1. **Pick one criterion.** Start with the one everything else depends on (usually the data or
   domain layer), not the most interesting one.
2. **Red.** Write the smallest test that expresses the criterion. Run it. Confirm it fails
   *for the right reason* (assertion failure, missing function) - not a typo, import error or
   broken fixture. A test you never saw fail proves nothing.
3. **Green.** Write the least production code that makes it pass. Hard-coding is fine for a
   moment if the next test will force the real logic.
4. **Refactor.** With the bar green, remove duplication, rename, extract. Run the tests again.
   No behavior changes during refactor.
5. **Commit.** One conventional commit per green step or per finished criterion.
6. Repeat until every criterion has at least one test that would fail if the behavior broke.

Do not write all tests up front and then all code. Do not write all code and then backfill tests.

## Bugs: regression test first

For a `fix:` job, the first commit is a test that reproduces the bug and fails on the current
code. Only then change production code. Name the test after the behavior, not the ticket:

```go
func TestTransfer_RejectsNegativeAmount(t *testing.T) { ... }   // good
func TestBug4821(t *testing.T) { ... }                           // bad
```

If you cannot reproduce the bug in a test, say so in your result notes instead of guessing a fix.

## Test naming

Name tests as `<unit>_<behavior>_<condition>` or a readable sentence. The name should tell a
reviewer which criterion it covers.

```ts
it("shows an empty state when the user has no invoices", ...)
it("disables submit while the request is in flight", ...)
```

```python
def test_create_order_returns_409_when_sku_out_of_stock(client, sku_factory): ...
```

Reference the criterion in a comment when the mapping is not obvious: `// AC3`.

## Test shape

- Arrange / act / assert, visibly separated. One behavior per test.
- Table-driven or parametrized tests for input variations of the same behavior.
- Assert on outcomes (return values, rows in the DB, HTTP status + body, rendered text), not on
  which private helpers were called.
- Deterministic: inject clocks, random sources and ID generators. No `sleep`.
- Each test sets up its own data. Never depend on test order or leftover state.

## What to mock and what not to

| Layer | Use |
|---|---|
| Data access (queries, repositories, migrations) | **Real database** (testcontainers, docker compose service, or the domain's test DB). Mocking SQL hides the bugs that matter. |
| Your own domain logic | Real code. Never mock the unit under test or its in-process collaborators. |
| HTTP handlers | Real router + `httptest` / test client, real or faked service layer. |
| Third-party HTTP APIs (payments, email, tracker) | Fake at the network boundary (stub server, MSW, `respx`, recorded fixtures). |
| Time, randomness, UUIDs | Injected fakes. |
| Message queues, object storage | Local emulator if the domain provides one, otherwise an interface fake. |

Rule of thumb: mock what you do not own and what is slow or non-deterministic; run what you own.

## Commit cadence

Small commits on the job branch, conventional format:

```
test(orders): cover 409 when sku is out of stock
feat(orders): reject orders for out-of-stock skus
refactor(orders): extract stock check into inventory service
fix(auth): stop accepting expired refresh tokens
```

- `test:` commits may be red only if immediately followed by the `feat:`/`fix:` that greens them.
  The final branch head must be green.
- Never commit with skipped, focused (`.only`, `t.Skip`, `@pytest.mark.skip`) or commented-out
  tests to get past a failure.
- Generated code is committed in the same commit as the source change that produced it.

## Feedback from previous attempts

If the brief contains failing test output, gate output or review findings from an earlier
attempt, handle them first:

1. Turn each reported failure into a test (or confirm an existing test now covers it).
2. Fix, run the full suite, commit with a message that references the finding.
3. Only then continue with remaining criteria.

## Coverage

Aim for every changed line of logic to be exercised, not for a global percentage. Branches that
handle errors need tests too - a reviewer will ask "what happens when the insert fails?".
Check coverage of changed files before finishing (see `verification-loop`).

## When to stop

- Every acceptance criterion maps to at least one passing test.
- The full test suite (not just your new tests) passes.
- No TODOs in place of behavior the spec asked for.
- Anything the spec did not ask for is not built. Note ideas in `notes`, do not implement them.

## Anti-patterns that reviewers will reject

- Tests that assert the mock was called and nothing else.
- Snapshot tests used as the only proof of a criterion.
- Loosening an assertion or deleting a test to make the suite pass.
- Catch-all `try/except` or `recover()` added so a test stops failing.
- Tests that pass even when the production change is reverted. Check this for your key test:
  revert the change locally, watch it fail, restore.
