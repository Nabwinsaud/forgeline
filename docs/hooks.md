# Guard hooks

Forgeline's hooks (`hooks/guard.py`) run on every tool call, but **only in repos that have
`.factory/config.json`**. Everywhere else they exit immediately.

Profile: `FORGELINE_HOOK_PROFILE` env › `.factory/config.json → hooks.profile` › `standard`.

| Guard | Who | minimal | standard | strict |
|---|---|:-:|:-:|:-:|
| Block `git push --force` / `-f` / `+ref` | everyone | ✓ | ✓ | ✓ |
| Block recursive delete of `/`, `~`, `.` | everyone | ✓ | ✓ | ✓ |
| Block `DROP DATABASE` / `DROP SCHEMA` | everyone | ✓ | ✓ | ✓ |
| Block `git reset --hard` outside a job worktree | everyone | ✓ | ✓ | ✓ |
| Block pushing to the base branch | factory agents | ✓ | ✓ | ✓ |
| Block `gh pr merge`, `gh issue close/edit` | factory agents | ✓ | ✓ | ✓ |
| Block edits to `.factory/checks.sh`, `config.json`, `pipeline.json`, `state/` | factory agents | ✓ | ✓ | ✓ |
| Block edits to generated code (`Code generated … DO NOT EDIT`, `@generated`) | everyone | | ✓ | ✓ |
| Block high-confidence secrets (AWS, GitHub, Slack, Stripe, private keys, API keys) | everyone | | ✓ | ✓ |
| gofmt hint after editing `.go` files | everyone | | ✓ | ✓ |
| Session briefing (jobs, what waits on you) | everyone | | ✓ | ✓ |
| Block `git commit --no-verify` | everyone | | | ✓ |
| Block `curl … \| sh` | everyone | | | ✓ |
| Block writing `.env` files | everyone | | | ✓ |
| Block hard-coded `password = "…"` style credentials | everyone | | | ✓ |

"Factory agents" means a Forgeline subagent (`agent_type` starts with `forgeline`) or any session working
inside `.factory/worktrees/`. A human driving Claude Code keeps normal control of their own repo.

Hooks fail open: a bug in the guard prints a warning and never blocks your work.
Blocking hooks exit with code 2; Claude sees the reason and adapts.
