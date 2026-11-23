# Contributing to Forgeline

## Layout
- `.claude-plugin/`: plugin + marketplace manifests
- `agents/`: factory roles (plugin subagents). Generic only; domain content belongs in an app's `.factory/`.
- `skills/`: command skills (`run`, `init`, …) and engineering skills
- `hooks/`: `hooks.json` + `guard.py` (stdlib, fail-open)
- `forgeline/`: engine, CLI, policy, prompt composition, adapters (Python 3.10+, **stdlib only**)
- `defaults/`: default config and pipeline; `templates/`: `.factory` scaffold and gate snippets
- `rules/`: rule packs copied into app repos by `forgeline init`

## Principles
- Agents judge, code decides. Transitions live in `pipeline.json`; merge rules only in `forgeline/policy.py`.
- New tracker / vcs / env = a new adapter file, no engine special cases.
- Hooks never break a session: fail open on internal errors, only act in repos with `.factory/`.
- No credentials in any file; adapters read env vars.

## Checks
```bash
python3 -m unittest discover -s tests
claude plugin validate . --strict
```
