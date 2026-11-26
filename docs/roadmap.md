# Roadmap

## v0.2 (now)
- Claude Code plugin + marketplace in one repo; `forgeline` CLI on PATH
- Runs from inside any app repo (`.factory/`), no registration
- 12 factory agents as real subagents with tool limits, models and preloaded skills
- 7 command skills + 13 engineering skills, rule packs for common / Go / TypeScript / Python
- Guard hooks with minimal / standard / strict profiles
- Stack detection and generated deterministic gate (`forgeline init`)
- Headless runner (`forgeline run`, Claude or Codex) with real cost capture; `forgeline report`, `doctor`
- Adapters: tracker local/github/jira/linear, vcs local/github, env none/url_poll/command

## Next

The to-do list for the next release is in
[next-iteration.md](next-iteration.md).

1. Battle-test the GitHub, Jira and Linear adapters against real projects.
2. GitHub Action template: run the factory on a schedule or on `factory:ready` labels.
3. Webhooks instead of polling (PR checks, review comments, deploy events).
4. GitLab and Bitbucket VCS adapters; Azure Boards and Shortcut trackers.
5. Per-role runner choice (e.g. Claude builds, Codex cross-reviews).
6. Agent SDK service for always-on cloud factories.
7. Read-only dashboard over `.factory/state` (throughput, pass rates, cost per ticket).
