---
name: init
description: Set up Forgeline in the current app repo - detect the stack, generate the deterministic gate, scaffold the domain harness (.factory/) and install rule packs, then help the user describe their business. Use when the user wants to start using the factory in a repo.
argument-hint: "[--tracker local|github|jira|linear] [--rules auto|none|go,typescript,python]"
disable-model-invocation: true
---

# Set up Forgeline in this repo

1. Confirm the repo root with `git rev-parse --show-toplevel`. If `.factory/config.json`
   already exists, ask before passing `--force` (it overwrites their edits).
2. Run `forgeline init $ARGUMENTS` and show the summary.
3. Interview the user briefly (max 6 questions, skip what the code already answers) to fill
   `.factory/domain.md`:
   - What the product does and who uses it.
   - The 3–5 business rules that must never break (invariants).
   - Which areas are high risk (auth, billing, personal data, migrations…).
   - Words with special meaning in this business (glossary).
   - Test accounts / test data QA may use on dev and stg (names of env vars, never secrets).
   Read the codebase to propose answers first; let the user correct them. Replace the
   template text in `domain.md` with the real content.
4. Open `.factory/checks.sh` and make sure every command exists in this repo (scripts in
   package.json, sqlc config, etc.). Run it once on the current branch: `bash .factory/checks.sh`.
   Fix the script (not the app) until it reflects how this repo is really verified.
5. Ask which tracker and git host they use. Fill `.factory/config.json` `tracker` / `vcs`
   from the `$examples` there. Credentials go in env vars only.
6. Keep `policy.auto_merge_max_risk` at `"none"` for now and tell them why: watch a few
   tickets first, then raise it to `"low"`.
7. Run `forgeline doctor`. Suggest committing `.factory/` and `.claude/rules/forgeline/`.
8. Suggest a first small ticket: `forgeline ticket add "..."`, then `/forgeline:run`.
