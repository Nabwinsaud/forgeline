# Forgeline rules

Rules are short, always-loaded engineering standards. Skills are loaded on demand and explain
*how*; rules state *what must always hold*. Every factory agent working in an app repo sees them,
and so does any human or assistant working in that repo with Claude Code.

## Packs

| Pack | Files | Included |
|---|---|---|
| `common` | coding-style, testing, security, git, agent-boundaries | always |
| `go` | coding-style, testing, security, sqlc | on request |
| `typescript` | coding-style, react, testing, security | on request |
| `python` | coding-style, testing, security | on request |

## Installing

```bash
forgeline init --rules go,typescript
```

This copies `common/` plus the named packs into the app repo at
`.claude/rules/forgeline/<pack>/`. `common` is always included, whether or not you list it.
Running it again overwrites the Forgeline copies only; your own files elsewhere in
`.claude/rules/` are untouched.

## Customizing

- Do not edit the copied files to add app-specific rules - they are replaced on upgrade.
  Put business rules and invariants in the domain harness (`.factory/domain.md`) and any extra
  repo conventions in your own `.claude/rules/*.md`.
- If the domain harness and a rule disagree, the domain harness wins for that app.
- Keep rules imperative and short. Long explanations belong in a skill.
