---
name: learn
description: Learn from past Forgeline jobs - turn recurring reviewer findings into domain rules or gate checks, spot flaky checks, and show what tickets cost. Use when the user says /forgeline:learn, asks what the factory keeps getting wrong, or wants the harness to improve itself.
---

1. Run `forgeline learn --json`.
2. For each item in `recurring_findings`, read 1-2 of its jobs' results under
   `.factory/state/jobs/<job>/results/` to understand the real problem. Then decide where it belongs:
   - **A check** in `.factory/checks.sh` if a command can catch it (a grep, a lint rule, a test).
     That's best: it's caught every time, for free.
   - **A rule** in `.factory/domain.md` if it needs judgement. One line, written as an instruction
     ("Money amounts are always ledger.Paisa, never float"), plus the reason.
   - **Nothing** if it was a one-off or is already covered.
3. For `flaky_gate`, find the failing check in the summary and suggest a fix (or a retry wrapper)
   in `checks.sh`.
4. Show the user the proposed edits as a short list, with the file and exact text. Apply them only
   after they say yes. Then run `forgeline doctor` and, if `checks.sh` changed, run it once.
