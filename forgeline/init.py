"""`forgeline init`: scaffold the domain harness (.factory/) in the current app repo.

Detects the stack (Go, Node/TypeScript, Python, or a mix in subfolders), generates a
matching deterministic gate, writes a starter config, and optionally installs rule packs.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .util import DOMAIN_DIRNAME, PLUGIN_ROOT, TEMPLATES_DIR, FactoryError, git_root, load_json, write_json

MARKERS = {
    "go": ["go.mod"],
    "node": ["package.json"],
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
}
RULE_PACKS = {"go": "go", "node": "typescript", "python": "python"}
FRONTEND_HINTS = ("vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs", "index.html")
CANDIDATE_DIRS = [".", "backend", "frontend", "web", "api", "server", "client", "app", "ui", "services"]


def detect(repo: Path) -> list[dict]:
    """Return components: [{"dir": "backend", "lang": "go", "area": "backend"}, ...]."""
    found = []
    for d in CANDIDATE_DIRS:
        p = repo / d
        if not p.is_dir():
            continue
        for lang, files in MARKERS.items():
            if any((p / f).exists() for f in files):
                if d == "." and any(c["dir"] != "." for c in found):
                    continue
                found.append({"dir": d, "lang": lang, "area": _area(p, d, lang)})
    # a root marker plus subfolder markers: prefer the subfolders
    if len({c["dir"] for c in found}) > 1:
        found = [c for c in found if c["dir"] != "."] or found
    return found


def _area(path: Path, d: str, lang: str) -> str:
    if d in ("frontend", "web", "client", "ui"):
        return "frontend"
    if d in ("backend", "api", "server", "services"):
        return "backend"
    if lang == "node" and any((path / h).exists() for h in FRONTEND_HINTS):
        return "frontend"
    return "backend"


def render_checks(components: list[dict]) -> str:
    t = TEMPLATES_DIR / "checks"
    out = (t / "header.sh").read_text()
    if not components:
        out += "\n# No stack detected. Add your build / lint / test commands here.\necho 'TODO: add checks'; exit 1\n"
    for c in components:
        out += (t / f"{c['lang']}.sh").read_text().replace("__DIR__", c["dir"]).replace("__AREA__", c["area"])
    out += (t / "footer.sh").read_text()
    return out


def _commands(components: list[dict]) -> dict:
    cmds = {}
    for c in components:
        cd = "" if c["dir"] == "." else f"cd {c['dir']} && "
        key = c["area"]
        if c["lang"] == "go":
            cmds[f"{key}_test"] = f"{cd}go test ./..."
            cmds[f"{key}_lint"] = f"{cd}go vet ./..."
            cmds[f"{key}_codegen"] = f"{cd}go generate ./..."
        elif c["lang"] == "node":
            cmds[f"{key}_test"] = f"{cd}npm test"
            cmds[f"{key}_lint"] = f"{cd}npm run lint"
            cmds[f"{key}_build"] = f"{cd}npm run build"
        elif c["lang"] == "python":
            cmds[f"{key}_test"] = f"{cd}pytest -q"
            cmds[f"{key}_lint"] = f"{cd}ruff check ."
    if any(c["area"] == "frontend" for c in components):
        fe = next(c for c in components if c["area"] == "frontend")
        cd = "" if fe["dir"] == "." else f"cd {fe['dir']} && "
        cmds["e2e"] = f"{cd}npx playwright test"
    return cmds


def install_rules(repo: Path, packs: list[str]) -> list[str]:
    dest = repo / ".claude" / "rules" / "forgeline"
    installed = []
    for pack in ["common", *packs]:
        src = PLUGIN_ROOT / "rules" / pack
        if not src.is_dir():
            continue
        target = dest / pack
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        installed.append(pack)
    return installed


def run(force: bool = False, rules: str | None = "auto", tracker: str = "local",
        base_branch: str | None = None) -> dict:
    repo = git_root()
    if repo is None:
        raise FactoryError("not inside a git repository. Run `git init` first.")
    ddir = repo / DOMAIN_DIRNAME
    if (ddir / "config.json").exists() and not force:
        raise FactoryError(f"{ddir} already exists. Use --force to regenerate (your edits would be overwritten).")

    components = detect(repo)
    ddir.mkdir(exist_ok=True)
    for item in (TEMPLATES_DIR / "factory").iterdir():
        target = ddir / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
        elif item.name != "config.json" and (force or not target.exists()):
            shutil.copy2(item, target)

    cfg = load_json(TEMPLATES_DIR / "factory" / "config.json")
    areas: dict[str, list[str]] = {}
    for c in components:
        areas.setdefault(c["area"], []).append("" if c["dir"] == "." else c["dir"].rstrip("/") + "/")
    cfg["areas"] = areas or {"backend": [""]}
    cfg["commands"] = _commands(components)
    cfg["tracker"]["type"] = tracker
    if base_branch:
        cfg["vcs"]["base_branch"] = base_branch
    else:
        head = (repo / ".git" / "HEAD")
        if head.exists() and head.read_text().startswith("ref: refs/heads/"):
            cfg["vcs"]["base_branch"] = head.read_text().strip().split("/")[-1]
    write_json(ddir / "config.json", cfg)

    checks = ddir / "checks.sh"
    checks.write_text(render_checks(components))
    checks.chmod(0o755)
    (ddir / ".gitignore").write_text("state/\nworktrees/\n")

    packs: list[str] = []
    if rules and rules != "none":
        wanted = sorted({RULE_PACKS[c["lang"]] for c in components}) if rules == "auto" else \
            [r.strip() for r in rules.split(",") if r.strip()]
        packs = install_rules(repo, wanted)

    return {"repo": str(repo), "components": components, "areas": cfg["areas"], "rules": packs,
            "base_branch": cfg["vcs"]["base_branch"], "files": sorted(p.name for p in ddir.iterdir())}


def summary(result: dict) -> str:
    lines = [f"Forgeline initialised in {result['repo']}/.factory/", ""]
    if result["components"]:
        lines.append("Detected:")
        for c in result["components"]:
            lines.append(f"  {c['dir']:<12} {c['lang']:<7} -> area {c['area']}")
    else:
        lines.append("No stack detected: edit .factory/checks.sh by hand.")
    lines += [f"Base branch: {result['base_branch']}",
              f"Rules installed: {', '.join(result['rules']) or 'none'} (.claude/rules/forgeline/)", "",
              "Next:",
              "  1. Describe your business in .factory/domain.md (rules, invariants, risky areas)",
              "  2. Review .factory/checks.sh (your merge gate) and .factory/config.json",
              "  3. forgeline doctor",
              '  4. forgeline ticket add "Your first small task"   then in Claude Code:  /forgeline:run']
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(detect(Path.cwd()), indent=2))
