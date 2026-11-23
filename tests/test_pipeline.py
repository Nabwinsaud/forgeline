"""End-to-end pipeline tests with a simulated agent crew.  python3 -m unittest discover tests"""
import unittest
from pathlib import Path

from helpers import Crew, git, make_repo, use_repo

from forgeline import config, engine, state, trackers
from forgeline.adapters.tracker_local import LocalTracker
from forgeline.util import load_json


def add_ticket(title, body=""):
    return LocalTracker({}, config.project()["name"]).add(title, body)


class PipelineTest(unittest.TestCase):
    def test_low_risk_ships_end_to_end_with_review_loop(self):
        repo = make_repo("ship")
        t = add_ticket("Say hello", "Add backend/hello.txt")
        job_id = trackers.pull()[0]["id"]

        crew = Crew(script={("review", 1, "code-reviewer"): ("changes_requested",
                                                            {"findings": [{"issue": "rename var"}]})})
        crew.run_until_idle()
        job = state.load(job_id)

        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        self.assertEqual(job["attempts"]["build"], 2)
        brief2 = (state.briefs_dir(job_id) / "build.2.backend-builder.md").read_text()
        self.assertIn("rename var", brief2)                       # reviewer feedback reached the builder
        self.assertIn("AC1: hello exists", brief2)                # spec from spec-writer result is shared
        self.assertNotIn(("build", 1, "frontend-builder"), crew.seen)  # area filter
        self.assertIn(("review", 1, "domain-business-rules"), crew.seen)  # domain reviewer joined
        self.assertEqual(git(repo, "show", "main:backend/hello.txt"), "attempt 2")
        ticket = load_json(repo / ".factory" / "tickets" / f"{t['key']}.json")
        self.assertEqual(ticket["status"], "done")
        self.assertFalse(Path(job["worktree"]).exists())          # worktree cleaned up

    def test_medium_risk_waits_for_human_then_merges(self):
        repo = make_repo("medium")
        add_ticket("Medium change")
        job_id = trackers.pull()[0]["id"]
        crew = Crew(risk="medium")
        crew.run_until_idle()
        job = state.load(job_id)
        self.assertEqual((job["status"], job["paused_stage"]), ("awaiting_human", "merge"))
        self.assertNotIn("backend/hello.txt", git(repo, "ls-tree", "-r", "main", "--name-only"))

        engine.human(job_id, "approve", note="reviewed the PR")
        crew.run_until_idle()
        self.assertEqual(state.load(job_id)["status"], "complete")

    def test_new_repo_default_policy_never_auto_merges(self):
        make_repo("safe", policy={"auto_merge_max_risk": "none"})
        add_ticket("Tiny change")
        job_id = trackers.pull()[0]["id"]
        Crew(risk="low").run_until_idle()
        self.assertEqual(state.load(job_id)["status"], "awaiting_human")

    def test_gate_failure_loops_then_blocks(self):
        make_repo("gatefail", gate="echo nope; exit 1")
        add_ticket("Never passes")
        job_id = trackers.pull()[0]["id"]
        Crew().run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "blocked")
        self.assertIn("max attempts", job["status_reason"])

    def test_intake_reject(self):
        make_repo("reject")
        add_ticket("Nonsense")
        job_id = trackers.pull()[0]["id"]
        Crew(script={("intake", 1, "intake"): ("reject", {})}).run_until_idle()
        self.assertEqual(state.load(job_id)["status"], "rejected")

    def test_resume_completes_results_left_by_a_dead_session(self):
        make_repo("resume")
        add_ticket("Resume me")
        job_id = trackers.pull()[0]["id"]
        tasks = engine.dispatch()
        from forgeline.util import write_json
        write_json(Path(tasks[0]["result_path"]), {"status": "pass", "summary": "ok",
                                                   "data": {"risk": "low", "areas": ["backend"]}})
        # session "dies" here without calling complete(); the next dispatch picks it up
        engine.dispatch()
        job = state.load(job_id)
        self.assertNotEqual(job["stage"], "intake")

    def test_tasks_carry_plugin_subagent_types(self):
        make_repo("types")
        add_ticket("Types")
        trackers.pull()
        task = engine.dispatch()[0]
        self.assertEqual(task["subagent_type"], "forgeline:intake")
        self.assertTrue(task["role_path"].endswith("agents/intake.md"))


if __name__ == "__main__":
    unittest.main()
