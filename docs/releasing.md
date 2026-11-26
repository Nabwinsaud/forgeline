# Releasing

Releases are automatic and come from commit messages. Nobody edits version numbers by hand.

## Two things get released

| What | Tag | Version lives in |
|---|---|---|
| Forgeline (engine + Claude Code plugin) | `v0.3.0` | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `forgeline/__init__.py` |
| `create-forgeline` (npm CLI) | `create-forgeline-v0.1.0` | `packages/create-forgeline/package.json` |

Each one has its own `CHANGELOG.md` and only gets a new version when its own files change.
Changes under `packages/` never bump the plugin version, and the other way round.

## How it works

1. Write commits as [Conventional Commits](https://www.conventionalcommits.org/):
   - `fix: ...` → patch (0.2.0 → 0.2.1)
   - `feat: ...` → minor (0.2.0 → 0.3.0)
   - `feat!: ...` or a `BREAKING CHANGE:` footer → major (minor while we're below 1.0)
   - `docs:`, `chore:`, `test:`, `ci:` → no release
2. On every push to `main`, [release-please](https://github.com/googleapis/release-please) opens or
   updates a **release PR** per component, with the version bump and the changelog.
3. Merge the release PR when you want to ship. That creates the git tag and the GitHub release.
4. When the tag is `create-forgeline-v*`, the `publish-cli` job tests, builds and publishes to npm
   with provenance.

Config: `release-please-config.json` and `.release-please-manifest.json` (the last released
versions). Workflow: `.github/workflows/release.yml`.

## One-time setup

- Repo → Settings → Actions → General → turn on **Allow GitHub Actions to create and approve pull requests**.
- Add an npm automation token as the repo secret **`NPM_TOKEN`** (npmjs.com → Access Tokens).
- The baseline tag `v0.2.0` exists, so release-please counts from there.
