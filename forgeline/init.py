"""`forgeline init`: scaffold the domain harness (.factory/) in the current app repo.

Detects the stack (Go, Node/TypeScript, Python, or a mix in subfolders), generates a
matching deterministic gate, writes a starter config, and optionally installs rule packs.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .util import DOMAIN_DIRNAME, PLUGIN_ROOT, TEMPLATES_DIR, FactoryError, git_root, load_json, write_json

MARKERS = {
    "go": ["go.mod"],
    "node": ["package.json"],
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "ruby": ["Gemfile"],
}
RULE_PACKS = {"go": "go", "node": "typescript", "python": "python"}
FRONTEND_HINTS = ("vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs", "next.config.ts",
                  "svelte.config.js", "nuxt.config.ts", "astro.config.mjs", "index.html")
FRONTEND_DEPS = ("react", "vue", "svelte", "next", "nuxt", "@angular/core", "solid-js", "astro")
CANDIDATE_DIRS = [".", "backend", "frontend", "web", "api", "server", "client", "app", "ui", "services"]
MONOREPO_PARENTS = ["apps", "packages", "services", "cmd"]
MAKE_TARGETS = ("check", "lint", "test")


def _dirs(repo: Path) -> list[str]:
    dirs = list(CANDIDATE_DIRS)
    for parent in MONOREPO_PARENTS:
        if (repo / parent).is_dir():
            dirs += sorted(f"{parent}/{c.name}" for c in (repo / parent).iterdir()
                           if c.is_dir() and not c.name.startswith("."))
    return dirs


def detect(repo: Path) -> list[dict]:
    """Return components: [{"dir": "backend", "lang": "go", "area": "backend"}, ...]."""
    found = []
    for d in _dirs(repo):
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
    if not found:
        targets = make_targets(repo)
        if targets:
            found.append({"dir": ".", "lang": "make", "area": "backend", "targets": targets})
    return found


def make_targets(path: Path) -> list[str]:
    """Targets the repo already defines for checking itself (Makefile `check`/`lint`/`test`)."""
    mk = path / "Makefile"
    if not mk.exists():
        return []
    defined = set(re.findall(r"^([A-Za-z0-9_.-]+):", mk.read_text(errors="ignore"), re.M))
    if "check" in defined:
        return ["check"]
    return [t for t in ("lint", "test") if t in defined]


def ci_commands(repo: Path) -> list[str]:
    """`run:` lines from GitHub Actions that look like checks. Shown as hints, never executed blindly."""
    out: list[str] = []
    wf = repo / ".github" / "workflows"
    if not wf.is_dir():
        return out
    for f in sorted(list(wf.glob("*.yml")) + list(wf.glob("*.yaml"))):
        for m in re.finditer(r"^\s*(?:-\s*)?run:\s*(.+)$", f.read_text(errors="ignore"), re.M):
            cmd = m.group(1).strip().strip("'\"")
            if cmd in ("|", ">") or cmd in out:
                continue
            if re.search(r"\b(test|lint|check|vet|typecheck|tsc|clippy|fmt|format|build)\b", cmd):
                out.append(cmd)
    return out[:15]


def _area(path: Path, d: str, lang: str) -> str:
    if d in ("frontend", "web", "client", "ui"):
        return "frontend"
    if d in ("backend", "api", "server", "services"):
        return "backend"
    if lang == "node" and any((path / h).exists() for h in FRONTEND_HINTS):
        return "frontend"
    if lang == "node":
        pkg = load_json(path / "package.json", {}) or {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if any(dep in deps for dep in FRONTEND_DEPS):
            return "frontend"
    return "backend"


def _node_pm(path: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if (path / lock).exists():
            return pm
    return "npm"


GREENFIELD = """
# --- No code yet ---------------------------------------------------------------
# Nothing to build or test was found when this file was generated. The gate passes so the first
# ticket can create the project skeleton. Once it has, regenerate this file from the real stack:
#   forgeline init --checks-only
echo "no stack detected yet: run 'forgeline init --checks-only' once the project has code"
"""


def render_checks(components: list[dict], ci_hints: list[str] | None = None) -> str:
    t = TEMPLATES_DIR / "checks"
    out = (t / "header.sh").read_text()
    if not components:
        out += GREENFIELD
    for c in components:
        out += ((t / f"{c['lang']}.sh").read_text().replace("__DIR__", c["dir"]).replace("__AREA__", c["area"])
                .replace("__TARGETS__", " ".join(c.get("targets", []))))
    if ci_hints:
        out += ("\n# --- From your CI (not run; uncomment what the gate should also check) ------------\n"
                + "".join(f"# {h}\n" for h in ci_hints))
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
            path = Path(c.get("_abs", c["dir"]))
            pm = _node_pm(path)
            scripts = (load_json(path / "package.json", {}) or {}).get("scripts", {})
            for name in ("test", "lint", "build", "typecheck"):
                if name in scripts:
                    cmds[f"{key}_{name}"] = f"{cd}{pm} {'test' if name == 'test' else 'run ' + name}"
        elif c["lang"] == "python":
            cmds[f"{key}_test"] = f"{cd}pytest -q"
            cmds[f"{key}_lint"] = f"{cd}ruff check ."
        elif c["lang"] == "rust":
            cmds[f"{key}_test"] = f"{cd}cargo test --all"
            cmds[f"{key}_lint"] = f"{cd}cargo clippy --all-targets -- -D warnings"
        elif c["lang"] == "java":
            cmds[f"{key}_test"] = f"{cd}" + ("./gradlew check" if (Path(c.get("_abs", c["dir"])) / "gradlew").exists()
                                             else "mvn -B verify")
        elif c["lang"] == "ruby":
            cmds[f"{key}_test"] = f"{cd}bundle exec rspec"
        elif c["lang"] == "make":
            for tgt in c.get("targets", []):
                cmds[f"{key}_{tgt}"] = f"{cd}make {tgt}"
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


def _write_checks(repo: Path, ddir: Path, components: list[dict]) -> None:
    checks = ddir / "checks.sh"
    checks.write_text(render_checks(components, ci_commands(repo)))
    checks.chmod(0o755)


def _areas(components: list[dict]) -> dict:
    areas: dict[str, list[str]] = {}
    for c in components:
        areas.setdefault(c["area"], []).append("" if c["dir"] == "." else c["dir"].rstrip("/") + "/")
    return areas or {"backend": [""]}


def refresh_checks() -> dict:
    """Re-detect the stack and rewrite checks.sh, areas and commands. Everything else is left alone.

    For repos that started empty (greenfield) and now have code, or that added a new service.
    """
    repo = git_root()
    if repo is None:
        raise FactoryError("not inside a git repository.")
    ddir = repo / DOMAIN_DIRNAME
    if not (ddir / "config.json").exists():
        raise FactoryError("no .factory/ yet. Run `forgeline init` first.")
    components = _detect_abs(repo)
    cfg = load_json(ddir / "config.json")
    cfg["areas"], cfg["commands"] = _areas(components), {**cfg.get("commands", {}), **_commands(components)}
    write_json(ddir / "config.json", cfg)
    _write_checks(repo, ddir, components)
    return {"repo": str(repo), "components": _public(components), "areas": cfg["areas"],
            "commands": cfg["commands"]}


def _detect_abs(repo: Path) -> list[dict]:
    comps = detect(repo)
    for c in comps:
        c["_abs"] = str(repo / c["dir"])
    return comps


def _public(components: list[dict]) -> list[dict]:
    return [{k: v for k, v in c.items() if not k.startswith("_")} for c in components]


def run(force: bool = False, rules: str | None = "auto", tracker: str = "local",
        base_branch: str | None = None) -> dict:
    repo = git_root()
    if repo is None:
        raise FactoryError("not inside a git repository. Run `git init` first.")
    ddir = repo / DOMAIN_DIRNAME
    if (ddir / "config.json").exists() and not force:
        raise FactoryError(f"{ddir} already exists. Use --force to regenerate (your edits would be overwritten), "
                           f"or `forgeline init --checks-only` to only re-detect the stack.")

    components = _detect_abs(repo)
    ddir.mkdir(exist_ok=True)
    for item in (TEMPLATES_DIR / "factory").iterdir():
        target = ddir / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
        elif item.name != "config.json" and (force or not target.exists()):
            shutil.copy2(item, target)

    cfg = load_json(TEMPLATES_DIR / "factory" / "config.json")
    cfg["areas"] = _areas(components)
    cfg["commands"] = _commands(components)
    cfg["tracker"]["type"] = tracker
    if base_branch:
        cfg["vcs"]["base_branch"] = base_branch
    else:
        head = (repo / ".git" / "HEAD")
        if head.exists() and head.read_text().startswith("ref: refs/heads/"):
            cfg["vcs"]["base_branch"] = head.read_text().strip().split("/")[-1]
    write_json(ddir / "config.json", cfg)

    _write_checks(repo, ddir, components)
    (ddir / ".gitignore").write_text("state/\nworktrees/\n")

    packs: list[str] = []
    if rules and rules != "none":
        wanted = sorted({RULE_PACKS[c["lang"]] for c in components if c["lang"] in RULE_PACKS}) if rules == "auto" else \
            [r.strip() for r in rules.split(",") if r.strip()]
        packs = install_rules(repo, wanted)

    return {"repo": str(repo), "components": _public(components), "areas": cfg["areas"], "rules": packs,
            "base_branch": cfg["vcs"]["base_branch"], "files": sorted(p.name for p in ddir.iterdir())}


def summary(result: dict) -> str:
    lines = [f"Forgeline initialised in {result['repo']}/.factory/", ""]
    if result["components"]:
        lines.append("Detected:")
        for c in result["components"]:
            lines.append(f"  {c['dir']:<12} {c['lang']:<7} -> area {c['area']}")
    else:
        lines.append("No code yet: the gate passes for now. After the first ticket adds a stack, run "
                     "`forgeline init --checks-only`.")
    lines += [f"Base branch: {result['base_branch']}",
              f"Rules installed: {', '.join(result['rules']) or 'none'} (.claude/rules/forgeline/)", "",
              "Next:",
              "  1. Describe your business in .factory/domain.md (rules, invariants, risky areas)",
              "  2. Review .factory/checks.sh (your merge gate) and .factory/config.json",
              "  3. forgeline doctor",
              '  4. forgeline do "Your first small task"   (or /forgeline:do in Claude Code)']
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(detect(Path.cwd()), indent=2))
