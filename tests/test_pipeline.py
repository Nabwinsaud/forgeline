"""End-to-end pipeline test with simulated agents. Stdlib only:  python3 -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sf-test-"))
os.environ["FACTORY_STATE_DIR"] = str(TMP / "state")
os.environ["FACTORY_CONFIG"] = str(TMP / "config.json")
sys.path.insert(0, str(ROOT))

from sf import engine, state, trackers  # noqa: E402
from sf.adapters.tracker_local import LocalTracker  # noqa: E402
from sf.util import load_json, write_json  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(name: str) -> Path:
    repo = TMP / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "factory@test"); git(repo, "config", "user.name", "factory")
    (repo / "README.md").write_text("app\n")
    git(repo, "add", "."); git(repo, "commit", "-qm", "init")
    shutil.copytree(ROOT / "domain-template" / ".factory", repo / ".factory")
    (repo / ".factory" / "checks.sh").write_text("#!/usr/bin/env bash\nset -e\ntest -f backend/hello.txt\n")
    cfg = load_json(repo / ".factory" / "config.json")
    cfg.pop("policy")  # use factory policy
    write_json(repo / ".factory" / "config.json", cfg)
    return repo


def setup_factory(*projects):
    base = load_json(ROOT / "factory" / "config.example.json")
    base["projects"] = [{"name": n, "repo_path": str(p)} for n, p in projects]
    write_json(TMP / "config.json", base)


class Sim:
    """Plays every agent. `script` maps (stage, attempt, agent) -> (status, data) overrides."""

    def __init__(self, risk="low", script=None):
        self.risk, self.script, self.seen = risk, script or {}, []

    def run_until_idle(self, max_ticks=60):
        for _ in range(max_ticks):
            tasks = engine.dispatch()
            if not tasks:
                return
            for t in tasks:
                self.seen.append((t["stage"], t["attempt"], t["agent"]))
                status, data = self.script.get((t["stage"], t["attempt"], t["agent"]), ("pass", {}))
                if t["stage"] == "intake":
                    data = {"risk": self.risk, "size": "small", "areas": ["backend"], **data}
                if t["agent"] == "backend-builder" and status == "pass":
                    wt = Path(t["cwd"])
                    (wt / "backend").mkdir(exist_ok=True)
                    (wt / "backend" / "hello.txt").write_text(f"attempt {t['attempt']}\n")
                    git(wt, "add", "."); git(wt, "commit", "-qm", f"feat: hello {t['attempt']}")
                write_json(Path(t["result_path"]), {"status": status, "summary": f"{t['agent']} {status}",
                                                    "data": data, "usage": {"cost_usd": 0.01}})
            for job_id in {t["job"] for t in tasks}:
                engine.complete(job_id)
        raise AssertionError("pipeline did not go idle")


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_repo("app")
        cls.app2 = make_repo("app2")
        setup_factory(("app", cls.app), ("app2", cls.app2))

    def test_low_risk_ships_end_to_end_with_review_loop(self):
        t = LocalTracker({}, "app").add("Say hello", "Add backend/hello.txt")
        jobs = trackers.pull("app")
        self.assertEqual(len(jobs), 1)

        sim = Sim(script={("review", 1, "code-reviewer"): ("changes_requested",
                                                           {"findings": [{"issue": "rename var"}]})})
        sim.run_until_idle()
        job = state.load(jobs[0]["id"])

        self.assertEqual(job["status"], "complete", json.dumps(job["history"], indent=1))
        self.assertEqual(job["attempts"]["build"], 2)  # review sent it back once
        brief2 = (state.briefs_dir(job["id"]) / "build.2.backend-builder.md").read_text()
        self.assertIn("rename var", brief2)  # reviewer feedback reached the builder
        self.assertNotIn(("build", 1, "frontend-builder"), sim.seen)  # area filter
        self.assertIn(("review", 1, "domain-business-rules"), sim.seen)  # domain reviewer joined
        self.assertEqual(git(self.app, "show", "main:backend/hello.txt"), "attempt 2")
        ticket = load_json(Path(os.environ["FACTORY_STATE_DIR"]) / "tickets" / "app" / f"{t['key']}.json")
        self.assertEqual(ticket["status"], "done")

    def test_medium_risk_waits_for_human_then_merges(self):
        LocalTracker({}, "app2").add("Medium change")
        job_id = trackers.pull("app2")[0]["id"]
        sim = Sim(risk="medium")
        sim.run_until_idle()
        job = state.load(job_id)
        self.assertEqual((job["status"], job["paused_stage"]), ("awaiting_human", "merge"))
        self.assertNotIn("hello.txt", git(self.app2, "ls-tree", "-r", "main", "--name-only"))

        engine.human(job_id, "approve", note="looks fine")
        sim.run_until_idle()
        self.assertEqual(state.load(job_id)["status"], "complete")

    def test_gate_failure_loops_then_blocks(self):
        repo = make_repo("app3")
        setup_factory(("app", self.app), ("app2", self.app2), ("app3", repo))
        (repo / ".factory" / "checks.sh").write_text("#!/usr/bin/env bash\necho nope; exit 1\n")
        LocalTracker({}, "app3").add("Never passes")
        job_id = trackers.pull("app3")[0]["id"]
        Sim().run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "blocked")
        self.assertIn("max attempts", job["status_reason"])


if __name__ == "__main__":
    unittest.main()
