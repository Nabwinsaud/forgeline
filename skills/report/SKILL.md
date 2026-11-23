---
name: report
description: Analyse Forgeline factory performance - pass rate, retries, time and cost per stage - and recommend model or prompt changes. Use when the user asks how the factory is doing or how to make it cheaper, faster or better.
---

1. Run `forgeline report --json` and `forgeline status --json`.
2. Find the weakest points:
   - stages with low pass rate or many attempts → weak role instructions or missing domain rules
   - recurring review findings → move the rule into `.factory/domain.md` or `.factory/checks.sh`
     (cheaper to catch early)
   - expensive stages that pass first time → try a cheaper model in `.factory/config.json` → `models`
   - jobs stuck in `awaiting_human` → policy too strict, or intake risk calls too cautious
3. Read a few briefs/results under `.factory/state/jobs/*/` to back each claim with evidence.
4. Give at most 5 concrete recommendations, each with the exact file and change. Do not apply
   them unless asked.
