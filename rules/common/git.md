# Git

- One branch per job. Work only on that branch, inside the job worktree.
- Commit small, focused changes with Conventional Commits:
  `type(scope): imperative summary` (feat, fix, test, refactor, perf, docs, build, ci, chore).
- Summary line at most 72 characters, no trailing period; body explains why.
- Mark breaking changes with `!` and a `BREAKING CHANGE:` footer.
- Each commit builds; the branch head passes the full test suite.
- Commit generated code together with the source change that produced it.
- Never commit secrets, `.env` files, credentials, build output, dependencies, coverage
  reports, editor folders or large binaries.
- Stage deliberately (`git add -p`) and read `git diff --cached` before committing.
- Leave the working tree clean at the end of a stage; the gate rejects uncommitted changes.
- Never push to the base branch. Never force-push a shared branch.
- Never rewrite history that has been pushed unless explicitly told to.
- Never use `--no-verify` or disable hooks.
- Do not change git config, remotes, or hooks.
- Keep the branch current with base by rebase while unpushed, merge once a PR is open, unless
  the domain harness says otherwise; rerun verification afterwards.
- Resolve conflicts by understanding both sides, never by blanket "ours"/"theirs".
