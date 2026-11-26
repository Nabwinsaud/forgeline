# create-forgeline

Set up [Forgeline](https://github.com/Nabwinsaud/forgeline) in any repo with one command.

```sh
npm create forgeline
# or
bunx create-forgeline
npx create-forgeline
```

Run it from the root of the app you want the factory to work on.

## What it does

1. Checks the repo: it's a git repo, the working tree is clean, Python 3.10+ is there, and whether `gh` and `claude` are installed.
2. Asks where your tickets live: local, GitHub Issues, Jira or Linear. GitHub is picked up from your
   `origin` remote and `gh` login, so it needs no token.
3. Detects your stack (Go, Node/TypeScript, Python, or a mix in `backend/` and `frontend/`) and writes
   `.factory/` plus rule packs in `.claude/rules/forgeline/`.
4. Sets safe defaults: **auto-merge off**, protected paths for auth, migrations, CI and `.factory/`.
5. Runs your new gate (`.factory/checks.sh`) once, so you know it's green before any agent touches it.
6. Installs the Forgeline plugin in Claude Code (agents, guard hooks, `/forgeline:*` commands).
7. Tells you what's left: mainly writing your business rules in `.factory/domain.md`.

## Options

| Flag | |
|---|---|
| `-y`, `--yes` | no questions: local tracker, auto-merge off |
| `--tracker <type>` | `local` · `github` · `jira` · `linear` |
| `--no-plugin` | skip the Claude Code plugin install |
| `--skip-gate` | don't run `checks.sh` at the end |

## Needs

Node 20+ (or Bun), git, Python 3.10+. Claude Code to actually run the factory.

The Python engine ships inside this package, so each `create-forgeline` version sets up a matching
engine version.

## Develop

```sh
bun install
bun test          # unit tests + a real scaffold into a temp repo
bun run typecheck
bun run lint
bun run build     # dist/cli.js + engine/ copied from the repo root
node dist/cli.js --help
```
