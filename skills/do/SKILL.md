---
name: do
description: Start a Forgeline job from one sentence and run it to a reviewed PR, with no tracker setup. Use when the user says /forgeline:do, "have the factory build X", or wants something built through the pipeline right now.
argument-hint: "<what you want built or fixed>"
---

1. If there is no `.factory/` in the repo, offer `/forgeline:init` and stop.
2. Turn `$ARGUMENTS` into a ticket. Keep the user's intent and don't invent requirements.
   - Title: imperative, under 70 characters.
   - Body: **Problem**, **Desired behavior**, **Acceptance hints** (bullets), **Out of scope**.
   If the request is genuinely ambiguous, ask one short question first.
3. Run `forgeline do "<title>" --body "<body>" --queue` and show the job id.
4. Read `${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md` and follow it as the orchestrator, skipping
   `forgeline pull`, until the job is complete, blocked or waiting for a human.
