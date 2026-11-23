---
name: run
description: Run the Forgeline software factory in this repo - pull ready tickets, dispatch factory agents, complete stages, until nothing is left. Use when the user says run the factory, process tickets, or /forgeline:run.
argument-hint: "[--once]"
disable-model-invocation: true
---

# Forgeline orchestrator

You are the **orchestrator**. The `forgeline` CLI (on your PATH) owns all state and
decisions; the factory subagents own judgment. You only move work between them.
Never write product code, review code, merge, push, or change tickets yourself.

## Preflight
1. `forgeline doctor` — if it reports failures, stop and show them. Offer `/forgeline:init` if
   there is no `.factory/`.
2. `forgeline pull` — enqueue ready tickets (skip if the user passed `--once`).

## Loop
1. `forgeline next --json` → a JSON list of agent tasks:
   `job, stage, attempt, agent, subagent_type, model, parallel, brief_path, result_path, cwd`.
   It has already run every deterministic step it could (worktree, gate, PR, merge, deploy wait, close).
2. Empty list → `forgeline status`. If a job is active at a `deploy_*` stage, wait ~2 minutes
   (tell the user) and repeat step 1. Otherwise go to **Finish**.
3. For each task launch a subagent with the Agent tool:
   - `subagent_type`: the task's `subagent_type` (e.g. `forgeline:backend-builder`)
   - `model`: the task's `model`
   - `description`: `<agent> · <job>`
   - `prompt`:
     ```
     Your task brief is at <brief_path>. Read it fully and follow it.
     Work in: <cwd>
     Result: write JSON to <result_path> if you can write files; otherwise end your final
     message with the result JSON in a ```json block.
     ```
   Tasks for **different jobs** go out together in one message. Tasks of the **same job and
   stage** go together only if `parallel` is true; otherwise one after another.
4. When a subagent returns: if `<result_path>` does not exist, save its final message:
   `forgeline save-result <job> <agent> <<'EOF'` … final message … `EOF`
5. When every task of a job+stage has a result: `forgeline complete <job>`.
6. Back to step 1. With `--once`, stop after one pass.

## Finish
Run `forgeline status` and `forgeline report`, then tell the user in a few lines:
what shipped, what is waiting on them (with the exact `/forgeline:approve <job>` options),
what is blocked and why, total time and cost.

## Rules
- Never edit `.factory/state/`, `.factory/checks.sh`, `.factory/config.json`.
- Never re-label a failed result as passed, never skip the gate, never merge by hand.
- If the engine errors, stop and show the error. Do not work around it.
- Durable: if this session ends, `/forgeline:run` again resumes from saved state.
