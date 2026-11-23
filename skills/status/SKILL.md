---
name: status
description: Show Forgeline factory jobs in this repo - where each ticket is, what is waiting on a human, what is blocked and why, time and cost. Use when the user asks about factory progress or a specific job.
argument-hint: "[job-id]"
---

Run `forgeline status $ARGUMENTS` (and `forgeline report` when no job id is given).

Summarise:
- counts per status: active, awaiting_human, blocked, complete, rejected
- each job waiting on a human: the stage, the reason, links to the PR if any, and the exact
  options: `/forgeline:approve <job>` (approve | reject | retry)
- each blocked job: the failing stage and the last error in one line; for details point to
  `.factory/state/jobs/<job>/results/` and `briefs/`
- time and cost so far

Do not change anything.
