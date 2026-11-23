---
description: Show factory jobs, where each is, time and cost. Pass a job id for its full history.
argument-hint: "[job-id]"
---

Run `bin/factory status $ARGUMENTS` from the repo root and summarize:
- jobs per status (active / awaiting_human / blocked / complete / rejected)
- for any job waiting on a human: the stage, the reason (last history entry), and the exact
  `bin/factory human ...` command options.
Do not change anything.
