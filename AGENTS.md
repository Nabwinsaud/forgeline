# Forgeline for Codex and other agents

Forgeline is harness-neutral at its core: the `forgeline` CLI owns state, and each agent task is a
markdown brief plus a role file.

- Headless with Codex: `forgeline run --runner codex` (uses `codex exec` per task, sandbox `workspace-write`).
- Manual: `forgeline next --json` gives tasks with `brief_path`, `role_path`, `result_path`, `cwd`;
  run each with any agent, then `forgeline complete <job>`.

Contributors: see CONTRIBUTING.md.
