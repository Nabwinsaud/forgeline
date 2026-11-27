"""`forgeline doctor`: check that this machine and repo can run the factory."""
from __future__ import annotations

import os
import shutil
import sys

from . import config
from .util import FactoryError, run

OK, WARN, FAIL = "ok", "warn", "fail"


def checks() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    def add(status, name, detail=""):
        out.append((status, name, detail))

    add(OK if sys.version_info >= (3, 10) else FAIL, "python >= 3.10", sys.version.split()[0])
    for tool, need in (("git", FAIL), ("claude", WARN), ("codex", None), ("gh", None), ("gitleaks", None)):
        found = shutil.which(tool)
        if found:
            add(OK, tool, found)
        elif need:
            add(need, tool, "not on PATH")

    try:
        root = config.repo_root()
    except FactoryError as e:
        add(FAIL, ".factory/", str(e))
        return out
    add(OK, "repo", str(root))

    for p in config.validate():
        add(FAIL, "config", p)

    dom = config.domain_config()
    base = dom["vcs"].get("base_branch", "main")
    if run(["git", "rev-parse", "--verify", "--quiet", base], cwd=root, check=False).returncode != 0:
        add(FAIL, "base branch", f"{base} does not exist")
    else:
        add(OK, "base branch", base)
    if dom["vcs"]["type"] == "local":
        cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, check=False).stdout.strip()
        if cur != base:
            add(WARN, "local merge", f"checkout is on {cur}; local merges need {base} checked out")

    t = dom["tracker"]
    if t["type"] == "github" or dom["vcs"]["type"] == "github":
        ok = shutil.which("gh") and run(["gh", "auth", "status"], check=False).returncode == 0
        add(OK if ok else FAIL, "gh auth", "logged in" if ok else "run `gh auth login`")
    if t["type"] == "jira":
        for var in (t.get("email_env", "JIRA_EMAIL"), t.get("token_env", "JIRA_API_TOKEN")):
            add(OK if os.environ.get(var) else FAIL, f"env {var}", "set" if os.environ.get(var) else "missing")
    if t["type"] == "linear":
        var = t.get("token_env", "LINEAR_API_KEY")
        add(OK if os.environ.get(var) else FAIL, f"env {var}", "set" if os.environ.get(var) else "missing")

    domain_md = (config.domain_dir() / "domain.md")
    if domain_md.exists() and "Delete these instructions" in domain_md.read_text():
        add(WARN, "domain.md", "still the template; agents know nothing about your business yet")

    checks_sh = config.domain_dir() / "checks.sh"
    if checks_sh.exists() and "forgeline init --checks-only" in checks_sh.read_text():
        from . import init
        if init.detect(root):
            add(WARN, "checks.sh", "the repo has code now but the gate checks nothing: run `forgeline init --checks-only`")
        else:
            add(WARN, "checks.sh", "no stack yet, so the gate checks nothing until the first ticket adds code")

    pol = {**config.factory_config().get("policy", {}), **dom.get("policy", {})}
    add(OK, "auto-merge", f"max risk = {pol.get('auto_merge_max_risk')}")
    return out


def report() -> int:
    rows = checks()
    icon = {OK: "✓", WARN: "!", FAIL: "✗"}
    for status, name, detail in rows:
        print(f" {icon[status]} {name:<16} {detail}")
    fails = sum(1 for r in rows if r[0] == FAIL)
    print(f"\n{'all good' if not fails else f'{fails} problem(s) to fix'}")
    return 1 if fails else 0
