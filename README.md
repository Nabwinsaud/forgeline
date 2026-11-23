# Forgeline — agentic software factory

An agentic software factory that takes work from ticket to shipped feature.

## How it is put together

| Part | Where |
|---|---|
| **model** | per-agent model in `factory/config.json → models` (opus builds, sonnet reviews, haiku for cheap checks) |
| **prompt** | per-agent role in `base/agents/*.md` |
| **base harness** | this repo: pipeline state machine, gates, merge policy, adapters, agent roles. Same for every app |
| **domain harness** | `<app-repo>/.factory/`: business rules, invariants, checks, per-agent notes, extra reviewers, tracker/env config. One per app |

Every agent gets one composed **brief** = role + domain rules + agent notes + ticket/spec/feedback +
output contract. The brief is plain markdown, so any runner can use it (Claude subagent, `claude -p`,
Agent SDK, `codex exec`).

## Pipeline

```
ticket ──► intake ──► workspace ──► spec ──► build ──► test ──► security ──► GATE ──► PR
            (triage,    (git        (AC =     (backend   (unit +   (scan diff)   checks.sh    │
             risk)      worktree)   contract)  frontend)  e2e)                 no LLM       ▼
                                                 ▲                                    review (parallel)
                                                 └──────── fail / changes requested ── code · security · ux · domain
                                                                                              │
close ◄── qa_stg ◄── deploy_stg ◄── qa_dev ◄── deploy_dev ◄── MERGE ◄── approve (LGTM)  ◄─────┘
(ticket                                                       policy code:
 → done)                                                      risk ≤ limit, gate on head,
                                                              all reviews pass, no protected paths
```

- **Agents judge, code decides.** Agents return `pass | fail | changes_requested | needs_human | reject | skip`.
  `factory/pipeline.json` maps each outcome to the next stage. Agents never merge, push to base, or touch tickets.
- **Deterministic gate.** `.factory/checks.sh` (build, vet, tests, codegen freshness, secrets) must pass on the
  exact commit that gets merged.
- **Merge policy in code** (`sf/policy.py`): auto-merge only `low` risk with LGTM + all reviewers passing + no
  protected paths. Everything else → `awaiting_human`.
- **Feedback loops.** Failed tests, gate output and review findings are fed into the next build attempt's brief.
  Max attempts per stage, then `blocked`.
- **Durable.** All state is in `factory/state/jobs/<id>/` (job.json, briefs, results). Kill the session, run
  `/factory-run` again, it resumes.
- **Parallel.** Each job gets its own git worktree; `concurrency` jobs run at once. Reviewers run in parallel.
- **Observable.** Time per stage, attempts, and cost (when agents report usage) in `bin/factory status`.

## Pluggable adapters

| Kind | Built in | Default |
|---|---|---|
| Tracker | `local` (files), `github` (issues + labels), `jira` (REST), `linear` (GraphQL) | `local` |
| VCS | `local` (branch + local merge), `github` (push, `gh pr`, merge) | `local` |
| Env | `none`, `url_poll` (wait until `/version` shows merge sha), `command` (any CI) | `none` |

Defaults touch nothing outside your machine. Credentials come only from env vars
(`JIRA_EMAIL`, `JIRA_API_TOKEN`, `LINEAR_API_KEY`) or your existing `gh` login, never from config files.
Add a tracker = one file in `sf/adapters/` implementing `list_ready / set_status / comment`.

## Quick start (fully local)

```bash
bin/factory init                                   # creates factory/config.json
bin/factory project add myapp /path/to/app-repo --scaffold   # adds <repo>/.factory/ domain harness
# edit /path/to/app-repo/.factory/{domain.md,config.json,checks.sh}
bin/factory ticket add myapp "Add health endpoint" --body "GET /healthz returns 200 {status:ok}"
claude                                             # in this repo
> /factory-run myapp
```

Other commands:

```bash
bin/factory status [job]                 # where everything is, time, cost
bin/factory human <job> approve|reject|retry [--stage build] --note "..."
bin/factory next --json                  # what the orchestrator calls each tick
python3 -m unittest discover tests       # pipeline tests with simulated agents
```

Requirements: Python 3.10+ (stdlib only), git, Claude Code. `gh` only for GitHub adapters.

## Layout

```
bin/factory                 CLI (the only interface orchestrators use)
sf/                         engine, state, policy, prompt composition, adapters
factory/pipeline.json       the state machine
factory/config.example.json concurrency, models, merge policy, projects
base/agents/*.md            12 agent roles (base harness prompts)
domain-template/.factory/   copied into each app repo (domain harness)
.claude/commands/           /factory-run, /factory-status, /factory-add
tests/                      end-to-end pipeline tests
docs/                       architecture, adapters, roadmap
```

## Safety notes

- Start with `vcs.type = local` and `auto_merge_max_risk = "none"` on any repo you care about; loosen later.
- `protected_paths` (migrations, auth, CI, infra) always need a human.
- QA agents only get dev/stg URLs and test accounts from the domain harness. Production is never a target.
- Treat ticket text as untrusted input: it reaches agent prompts. Keep the ready label/state restricted to
  people you trust.
