# Architecture

## Separation of duties

| Who | Owns | Never does |
|---|---|---|
| **Engine** (`forgeline/engine.py` + `pipeline.json`) | state, transitions, attempts, locks, script stages | judgment calls |
| **Policy** (`forgeline/policy.py`) | whether a merge is allowed | trust an agent's claim about risk alone |
| **Agents** (`agents/` plugin subagents + domain overlay) | judgment: triage, spec, code, tests, reviews, QA | merge, push base, change tickets, change state |
| **Orchestrator** (`/forgeline:run` or headless `forgeline run`) | moving tasks between engine and agents | decide outcomes |
| **Adapters** (`forgeline/adapters`, `vcs.py`, `envs.py`) | talking to trackers, git hosts, environments | pipeline logic |
| **Guard hooks** (`hooks/guard.py`) | blocking unsafe tool calls in factory repos | business decisions |

## Job lifecycle

```
dispatch():
  for each active job:
    lock held? -> results all present? complete() : (stale? re-hand-out missing : wait)
    run script stages until an agent stage / pending / terminal
    claim agent stage: attempt += 1 (or block at max), resolve agents (area filter + domain reviewers),
                       compose briefs, lock, return tasks
complete(job):
  read results for the locked attempt, worst status wins
  (needs_human > reject > fail > changes_requested > pending > pass; skip == pass)
  apply side effects (risk/areas from intake+spec, PR comments)
  transition via pipeline.json, sync tracker status
```

## Files per job

```
.factory/state/jobs/<id>/
  job.json                      the job (stage, status, attempts, lock, history, pr, shas)
  spec.md                       written by spec-writer, fed to every later agent
  briefs/<stage>.<n>.<agent>.md exactly what the agent saw (audit / debugging)
  results/<stage>.<n>.<agent>.json what the agent returned
.factory/tickets/            local tracker only
```

## Model + prompt tuning loop

Because every brief and result is stored, you can measure the factory:
- pass rate and attempts per stage → which agent prompt is weak
- time and cost per stage (`forgeline report`) → which model to downgrade/upgrade in `models`
- review findings that recur → move the rule into `domain.md` or `checks.sh` (shift left)
