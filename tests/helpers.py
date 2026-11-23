"""Shared test helpers: temp git repos and a simulated agent crew."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="forgeline-test-"))
os.environ["FORGELINE_HOME"] = str(TMP / "home")  # never read the developer's own config
sys.path.insert(0, str(ROOT))

from forgeline import config, engine, init  # noqa: E402
from forgeline.util import load_json, write_json  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def use_repo(repo: Path):
    os.environ["FORGELINE_REPO"] = str(repo)
    config.reload()


def make_repo(name: str, gate: str = "test -f backend/hello.txt", policy: dict | None = None) -> Path:
    repo = TMP / name
    (repo / "backend").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "factory@test")
    git(repo, "config", "user.name", "factory")
    (repo / "backend" / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    cwd = os.getcwd()
    os.chdir(repo)
    try:
        os.environ.pop("FORGELINE_REPO", None)
        init.run(rules="none")
    finally:
        os.chdir(cwd)
    (repo / ".factory" / "checks.sh").write_text(f"#!/usr/bin/env bash\nset -e\n{gate}\n")
    cfg = load_json(repo / ".factory" / "config.json")
    cfg["policy"] = policy or {"auto_merge_max_risk": "low", "protected_paths": []}
    write_json(repo / ".factory" / "config.json", cfg)
    git(repo, "add", ".factory")
    git(repo, "commit", "-qm", "factory")
    use_repo(repo)
    return repo


class Crew:
    """Plays every factory agent. `script` maps (stage, attempt, agent) -> (status, data)."""

    def __init__(self, risk="low", script=None):
        self.risk, self.script, self.seen = risk, script or {}, []

    def run_until_idle(self, max_ticks=80):
        for _ in range(max_ticks):
            tasks = engine.dispatch()
            if not tasks:
                return
            for t in tasks:
                self.seen.append((t["stage"], t["attempt"], t["agent"]))
                status, data = self.script.get((t["stage"], t["attempt"], t["agent"]), ("pass", {}))
                if t["stage"] == "intake":
                    data = {"risk": self.risk, "size": "small", "areas": ["backend"], **data}
                if t["stage"] == "spec":
                    data = {"spec_markdown": "# Spec\n\nAC1: hello exists", **data}
                if t["agent"] == "backend-builder" and status == "pass":
                    wt = Path(t["cwd"])
                    (wt / "backend" / "hello.txt").write_text(f"attempt {t['attempt']}\n")
                    git(wt, "add", ".")
                    git(wt, "commit", "-qm", f"feat: hello {t['attempt']}")
                write_json(Path(t["result_path"]), {"status": status, "summary": f"{t['agent']} {status}",
                                                    "data": data, "usage": {"cost_usd": 0.01}})
            for job_id in {t["job"] for t in tasks}:
                engine.complete(job_id)
        raise AssertionError("pipeline did not go idle")
