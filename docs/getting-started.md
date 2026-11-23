# Getting started

This walks one real repo from zero to its first shipped ticket.

## 1. Install the plugin (once per machine)

```text
/plugin marketplace add Nabwinsaud/forgeline
/plugin install forgeline@forgeline
```

Check: `/plugin` lists `forgeline`, and in a shell inside Claude Code `forgeline version` works.

## 2. Initialise your app repo

Open Claude Code in your app repo and run `/forgeline:init`. It:

1. Detects your stack (Go, Node/TypeScript/React, Python, alone or in `backend/` + `frontend/` style folders).
2. Writes `.factory/`: `config.json`, a stack-specific `checks.sh` gate, `domain.md`, `reviewers/`, `agents/`.
3. Installs rule packs into `.claude/rules/forgeline/` (common plus your languages).
4. Interviews you to fill `domain.md` with your real business rules.
5. Runs your gate once and fixes the *script* until it matches how your repo is really verified.

CLI equivalent: `forgeline init [--tracker github] [--rules go,typescript]`.

Commit `.factory/` and `.claude/rules/forgeline/` so your team shares the same factory.

## 3. Describe your business

`.factory/domain.md` is what every agent reads before doing anything. Good content:

```markdown
## Invariants (never break)
- A booking slot can never be double-booked.
- Every query on tenant data filters by tenant_id.

## High-risk areas (always need a human)
- backend/internal/billing/, backend/internal/auth/
```

Add domain experts as reviewers in `.factory/reviewers/` and list them in `config.json → domain_reviewers`.

## 4. Connect your tools (optional; local works out of the box)

| Tracker | config.json | Credentials |
|---|---|---|
| local | `"type": "local"` | none: `forgeline ticket add` |
| GitHub Issues | `"type": "github", "repo": "owner/app"` | `gh auth login` |
| Jira | `"type": "jira", "base_url", "jql", "status_map"` | `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| Linear | `"type": "linear", "team_key", "ready_state"` | `LINEAR_API_KEY` |

Git host: `vcs.type = "github"` opens real PRs; `local` merges into your local base branch.
Environments: `envs.dev` / `envs.stg` as `url_poll` (waits until `/version` shows the merged commit) or
`command` (any script; exit 0 = deployed, 75 = not yet).

Run `forgeline doctor` after every change.

## 5. First ticket

```text
/forgeline:ticket add GET /healthz returning {"status":"ok"}
/forgeline:run
```

Watch `forgeline status`. The job runs intake → spec → build → test → security → gate → PR → review →
approve, then stops at `awaiting_human`, because new repos start with auto-merge off. Review the PR and run
`/forgeline:approve <job>`.

## 6. Turn it up

After a few good tickets:

- `policy.auto_merge_max_risk: "low"`: low-risk tickets merge themselves.
- `forgeline run` headless from cron or CI for unattended runs.
- `/forgeline:report`: shows where the factory spends time and money, and what to tune.
