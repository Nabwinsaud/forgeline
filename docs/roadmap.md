# Roadmap

## Done (v0.1)
- Deterministic engine, 15-stage pipeline, durable state, per-job worktrees, concurrency limit
- 12 base agent roles; domain harness overlay with extra domain reviewers
- Merge policy in code (risk, gate-on-head, reviewers, protected paths), human approve/reject/retry
- Adapters: tracker local/github/jira/linear, vcs local/github, env none/url_poll/command
- Claude Code orchestrator command `/factory-run`
- End-to-end tests with simulated agents

## Next
1. **Real-run hardening** — run against a sample React+Vite / Go+sqlc app; tune agent prompts from results.
2. **Headless runner** — `bin/factory run --runner claude` using `claude -p --model <m>` per task, so the
   factory runs from cron/CI without an interactive session.
3. **Codex runner** — `--runner codex` via `codex exec`; per-agent runner choice in config
   (e.g. Claude builds, Codex cross-reviews).
4. **Agent SDK / cloud** — move the loop into a long-running service using the Claude Agent SDK.
5. **GitHub webhooks** — react to PR CI status and human review comments instead of polling.
6. **Cost capture** — record real token usage from the runner instead of agent self-reports.
7. **More adapters** — GitLab, Bitbucket, Azure Boards, Shortcut; Argo/Vercel/Fly deploy checks.
8. **Dashboard** — read-only view of `factory/state` (throughput, pass rates, cost per ticket).
