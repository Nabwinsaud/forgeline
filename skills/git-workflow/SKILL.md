---
name: git-workflow
description: Git conventions for factory jobs - one branch per job in its own worktree, small conventional commits, message format, what never to commit, keeping the branch current with base (rebase vs merge), never force-pushing shared branches, and the PR description shape. Use when committing, updating a job branch, or writing a PR description.
---

# Git workflow

Each job runs in its own git worktree on its own branch. The factory creates the branch, pushes
it, opens the PR and merges. **You commit; you never push to base, never merge, never close PRs.**

## Branch per job

- The branch already exists when you start (e.g. `forgeline/<job-id>-<slug>`). Stay on it.
- Do not create extra branches, switch to base, or check out other jobs' branches.
- Do not touch files outside the worktree.
- `git status` before you start: if the tree is dirty from a previous attempt, read what is there
  before discarding anything.

## Commits

Small, focused, each one builds and (except a deliberate red `test:` step) passes tests.

Format (Conventional Commits):

```
<type>(<scope>): <imperative summary, <= 72 chars, no period>

<optional body: why, not what; wrap at 72>

<optional footer: Refs: TICKET-123>
```

Types: `feat`, `fix`, `test`, `refactor`, `perf`, `docs`, `build`, `ci`, `chore`.
Breaking API change: `feat(api)!: ...` plus a `BREAKING CHANGE:` footer explaining migration.

Good:
```
feat(orders): reject orders with non-positive quantity
fix(auth): expire refresh tokens after rotation
test(invoices): cover empty state for new accounts
```

Bad: `update`, `fix stuff`, `WIP`, `address review comments` (say which issue you fixed).

When addressing feedback from a previous attempt, one commit per finding (or a clearly grouped
set) with a message that names it: `fix(orders): return 404 for other tenant's order (review)`.

## Never commit

- Secrets: `.env`, keys, tokens, credentials, private certs, kubeconfigs. If you accidentally
  committed one, do not just delete it in a later commit - report it in `notes` as needing
  rotation and history cleanup by a human.
- Build output, `node_modules`, `dist/`, coverage reports, `__pycache__`, `.DS_Store`, IDE folders.
- Large binaries or data dumps.
- Local config overrides, debugging scripts, scratch files.
- Unrelated changes (formatting sweeps of files you did not need to touch).

Generated code that the repo *does* track (sqlc output, OpenAPI clients) is committed together
with the source change that generated it, regenerated - never hand-edited.

```bash
git add -p              # stage deliberately
git diff --cached       # read what you are about to commit
git commit -m "feat(orders): ..."
```

## Keeping up with base

If the gate or the factory reports the branch is behind base or conflicts:

- **Unpushed / job-local branch:** rebase is preferred - linear history, easy review.
  ```bash
  git fetch origin
  git rebase origin/main
  # resolve conflicts, run tests, git rebase --continue
  ```
- **Branch already pushed with an open PR:** prefer `git merge origin/main` so you do not rewrite
  history that reviewers and the factory have already seen - unless the domain harness says
  rebase. The factory, not you, pushes the result.
- After either, rerun the full verification loop; a clean merge can still break behavior.
- Resolve conflicts by understanding both sides. Never resolve by blindly taking "ours" or
  "theirs" on files you did not write.

## History rules

- Never `git push --force` to base or to any branch someone else uses. Never push at all unless
  the brief explicitly gives you that job.
- Do not amend or rebase commits that were already pushed, unless the factory asks for it.
- No `git reset --hard` that discards work you have not inspected.
- Do not change git config, hooks, or remotes.
- No `--no-verify` to skip hooks.

## PR description shape

When asked to draft the PR body:

```markdown
## Summary
One paragraph: what changed and why. Link the ticket.

## Acceptance criteria
- [x] AC1 - <short> - covered by `TestCreateOrder_Happy`
- [x] AC2 - <short> - covered by `orders.spec.ts: AC2 ...`

## Changes
- API: POST /orders now validates quantity (422 invalid_quantity)
- DB: migration 0042 adds index on orders(customer_id, created_at)
- UI: OrderForm shows server field errors

## Risk
low | medium | high - why. Protected paths touched: migrations.

## Testing
Commands run and results. Anything manually verified.

## Notes for reviewers
Decisions, trade-offs, follow-ups deliberately left out of scope.
```

Keep it factual. No marketing, no claims you did not verify.
