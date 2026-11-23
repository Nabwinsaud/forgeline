# Software Factory — instructions for Codex and other agents

Same rules as `CLAUDE.md`. The factory is harness-neutral:

- The engine is `bin/factory` (plain CLI, JSON in/out).
- Each agent task is a markdown brief at `brief_path`; the agent writes JSON to `result_path`.

Codex orchestration (planned, see `docs/roadmap.md`):

```bash
bin/factory next --json | jq -c '.[]' | while read -r t; do
  codex exec --cd "$(jq -r .cwd <<<"$t")" \
    "Read $(jq -r .brief_path <<<"$t") and follow it. Write the result JSON to $(jq -r .result_path <<<"$t")."
done
# then: bin/factory complete <job> for each job
```
