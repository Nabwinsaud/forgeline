# Software Factory — instructions for Claude Code

This repo is the **base harness** of an agentic software factory. Read `README.md` for the model.

## When asked to run the factory
Use `/factory-run`. You are the orchestrator: you call `bin/factory`, spawn subagents with the
briefs it gives you, and call `bin/factory complete`. You never decide outcomes, merge, push, or
change tickets yourself.

## When asked to change the factory itself
- Python 3.10+, **stdlib only**. No third-party packages in `sf/`.
- State transitions live in `factory/pipeline.json`; keep `sf/engine.py` generic.
- Merge rules live only in `sf/policy.py`. Never let an agent result bypass it.
- New tracker / vcs / env = new adapter file; do not special-case in the engine.
- Agent role prompts live in `base/agents/`; domain-specific content never goes there — it belongs in
  an app repo's `.factory/`.
- Run `python3 -m unittest discover tests` after any engine change.

## Never
- Edit `factory/state/**/job.json` by hand.
- Put credentials in any config file. Adapters read them from env vars.
- Point QA or deploy adapters at production.
