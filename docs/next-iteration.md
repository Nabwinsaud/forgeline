# Next release: plan

What to work on next, most important first.

## 1. Rebase on latest main before merging
- [ ] `workspace`: fetch and branch from `origin/<base>`, not the local base branch
- [ ] `merge`: rebase the job branch on the latest base, re-run the gate, and only merge if it's green on the new head
- [ ] on a rebase conflict, send it back to `build` with the conflict as feedback instead of going straight to `blocked`

Today a job can branch from a stale local `main` and get merged without being tested against what
merged before it.

## 2. Keep push/PR credentials away from agents
- [ ] run agents without `GH_TOKEN` / `gh` auth in their environment; only the engine's `pr` and `merge` scripts push
- [ ] block `git push` and `gh pr create` from agents completely, not just pushes to main

If an agent can push or open PRs itself, the gate is only advice.

## 3. Make the hooks harder to get around
- [ ] `strict` profile: if the guard crashes, block the call instead of allowing it (fail closed)
- [ ] protect the hook config itself (`.claude/settings*.json`, the plugin's `hooks/`) from agent edits
- [ ] block `git commit --no-verify` for agents in `standard` too, not only `strict`

## 4. Stop the builder from weakening tests
- [ ] the gate flags diffs that delete or loosen existing tests/assertions, and those need a reviewer to sign off explicitly
- [ ] a "change the plan" request: the builder can ask to change the spec, and the job pauses until a human approves it

The spec is already out of the builder's reach, but tests live in source, and today drift is only
caught by reviewer judgment.

## 5. File leases for parallel jobs
- [ ] before `build`, a job takes a lease on the areas/paths it plans to touch (from the spec)
- [ ] a job whose paths overlap a running job waits instead of running alongside it

Until this exists, `concurrency: 1` is the safe setting when tickets touch the same code.

## 6. Clean up dead worktrees
- [ ] `forgeline prune`: remove worktrees and branches of jobs that are complete, rejected, or stale
- [ ] run it automatically on `forgeline run` start

## 7. Fast path for tiny tickets
- [ ] when intake says `size: trivial` and `risk: low`, skip the separate spec/test/security stages: one builder, the gate, one reviewer

## 8. Bugs
- [ ] Jira adapter: keep line breaks in lists and code blocks when reading ticket descriptions (ADF → text)
- [ ] release PRs get no CI, because release-please uses the built-in token. Use a GitHub App token so the required checks run
- [ ] `create-forgeline`: detect when `git push` uses a different GitHub account than `gh` and offer the per-repo fix

## Later
- [ ] README: say clearly what's different about Forgeline: business rules per repo (`domain.md`,
      domain reviewers, business checks in the gate) and merge policy in code
- [ ] team mode: self-hosted server, shared job state, sessions tied to tickets, humans only see opened PRs
