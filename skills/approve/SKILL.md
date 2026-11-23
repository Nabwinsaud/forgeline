---
name: approve
description: Record a human decision on a Forgeline job that is awaiting a human or blocked - approve, reject, or retry a stage. Use only when the user explicitly decides on a job.
argument-hint: "<job-id> [approve|reject|retry] [--stage build] [note]"
disable-model-invocation: true
---

1. Run `forgeline status <job>` and show the user why it paused (last history entry, reason,
   PR link, relevant findings from `.factory/state/jobs/<job>/results/`).
2. If the decision is not in `$ARGUMENTS`, ask: approve, reject, or retry (and which stage).
   - **approve** at `merge`: the human overrides the risk policy for this PR only.
   - **retry**: restarts a stage with a fresh attempt budget (default: the paused stage).
3. Run `forgeline human <job> <decision> [--stage <stage>] --note "<why>"`.
   The note is recorded in the job history; ask for one if the user gave none.
4. Offer to continue with `/forgeline:run`.

Never approve on the user's behalf.
