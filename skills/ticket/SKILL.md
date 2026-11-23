---
name: ticket
description: Turn a feature or bug request into a well-formed Forgeline ticket in this repo's local tracker. Use when the user wants to queue work for the factory without using GitHub, Jira or Linear.
argument-hint: "<what you want built or fixed>"
---

1. Check the tracker: `forgeline doctor` output or `.factory/config.json` → `tracker.type`.
   If it is not `local`, tell the user to create the ticket in their tracker with the ready
   label/state, then run `forgeline pull`. Stop.
2. Turn `$ARGUMENTS` into a ticket. Keep the user's intent; do not invent requirements.
   - Title: imperative, under 70 characters.
   - Body: **Problem**, **Desired behavior**, **Acceptance hints** (bullets), **Out of scope**.
   Ask one clarifying question only if the request is genuinely ambiguous.
3. `forgeline ticket add "<title>" --body "<body>"` and show the ticket key.
4. Offer `/forgeline:run`.
