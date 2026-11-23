---
name: doctor
description: Diagnose whether this machine and repo can run the Forgeline factory - tools, config, base branch, tracker credentials, domain harness completeness. Use when setup fails or before the first run.
---

Run `forgeline doctor`. For each ✗ explain the fix in one line and offer to apply the ones
that are file changes in `.factory/` (never set credentials yourself; tell the user which
environment variable to export). For ! warnings, explain the trade-off briefly.
