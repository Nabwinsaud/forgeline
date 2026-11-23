# Configuration

Three layers, later wins:

1. `defaults/config.json`: shipped with the plugin
2. `~/.config/forgeline/config.json`: you, on this machine (optional)
3. `<repo>/.factory/config.json`: this app (the domain harness)

## `.factory/config.json`

| Key | Meaning |
|---|---|
| `tracker` | `local` · `github` · `jira` · `linear` (see `$examples` in the file) |
| `vcs` | `local` (merge into local base branch) · `github` (`repo`, `base_branch`, `merge_method`, `draft`) |
| `envs.dev`, `envs.stg` | `none` · `url_poll` (`url`, `version_path`, `timeout_minutes`) · `command` (`command`, `timeout_minutes`) |
| `areas` | area → folders, e.g. `{"backend": ["backend/"], "frontend": ["frontend/"]}`; decides which builders run |
| `commands` | named commands agents should use (`backend_test`, `frontend_lint`, `e2e`, …) |
| `policy.auto_merge_max_risk` | `none` · `low` · `medium` · `high`. New repos: `none` |
| `policy.protected_paths` | globs that always require a human to merge |
| `hooks.profile` | `minimal` · `standard` · `strict` (see hooks.md) |
| `models` | per-role model override, e.g. `{"backend-builder": "opus", "ux-reviewer": "haiku"}` |
| `domain_reviewers` | `[{"name", "prompt": "reviewers/x.md", "model"}]`: run in parallel with the review stage |
| `concurrency` | jobs in flight at once (default 3) |
| `runner` | headless runner settings: `default`, `timeout_minutes`, `claude.permission_mode`, `codex.sandbox`, `codex.model` |

## Pipeline

Copy `defaults/pipeline.json` to `.factory/pipeline.json` to change stages or transitions for one repo,
for example to drop `stg`, add a second QA stage, or raise `max_attempts` for `build`.

## Models

Resolution per role: `.factory/config.json → models.<role>` › `~/.config/forgeline` › built-in role default
(`defaults/config.json`) › `models.default`. Built-in role defaults win over a repo-level `default`, so to make
every role cheap, set each role explicitly (or use `forgeline report` to pick which ones).


Defaults put judgment-heavy roles (spec, build, code review, approve) on `opus`, the rest on `sonnet`, and UX
review on `haiku`. Run `forgeline report` after a week and move roles down to cheaper models where pass
rates stay high.
