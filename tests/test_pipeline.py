"""End-to-end pipeline tests with a simulated agent crew.  python3 -m unittest discover tests"""
import unittest
from pathlib import Path

from helpers import Crew, git, make_repo, use_repo

from forgeline import config, engine, scripts, state, trackers
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


def commit_on_main(repo, path, text, msg):
    """Someone else merges to main while the job is in flight."""
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)
    git(repo, "add", path)
    git(repo, "commit", "-qm", msg)


class DoTest(unittest.TestCase):
    def test_do_ships_from_one_sentence(self):
        repo = make_repo("do")
        job = trackers.do("Say hello", "Add backend/hello.txt")
        self.assertEqual(trackers.pull(), [])                     # not enqueued twice
        Crew().run_until_idle()
        job = state.load(job["id"])
        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        ticket = load_json(repo / ".factory" / "tickets" / f"{job['ticket']['key']}.json")
        self.assertEqual(ticket["status"], "done")

    def test_do_uses_local_tickets_even_when_repo_uses_jira(self):
        repo = make_repo("do-jira")
        cfg = load_json(repo / ".factory" / "config.json")
        cfg["tracker"] = {"type": "jira", "site": "https://x.atlassian.net", "jql": "x"}
        from forgeline.util import write_json
        write_json(repo / ".factory" / "config.json", cfg)
        config.reload()
        job = trackers.do("Say hello")
        self.assertIsInstance(trackers.get_for(job), LocalTracker)


class QuestionsTest(unittest.TestCase):
    QS = {"questions": ["Should archived groups show? (default: no)", "Who can export? (default: admins)"]}

    def test_intake_asks_then_resumes_with_answers_in_every_brief(self):
        repo = make_repo("ask")
        t = add_ticket("Export groups")
        job_id = trackers.pull()[0]["id"]
        crew = Crew(script={("intake", 1, "intake"): ("needs_human", self.QS)})
        crew.run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "awaiting_human")
        self.assertTrue(job["questions"]["open"])
        ticket = load_json(repo / ".factory" / "tickets" / f"{t['key']}.json")
        posted = ticket["comments"][-1]["text"]
        self.assertTrue(posted.startswith("Forgeline has a few questions"))
        self.assertIn("2. Who can export? (default: admins)", posted)

        engine.answer(job_id, "No archived groups. Only admins.")
        crew.run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        brief = (state.briefs_dir(job_id) / "build.1.backend-builder.md").read_text()
        self.assertIn("Answers from the ticket author", brief)
        self.assertIn("Only admins.", brief)
        self.assertIn("Q: Who can export?", brief)

    def test_reply_on_the_ticket_resumes_the_job(self):
        repo = make_repo("ask-reply")
        t = add_ticket("Export groups")
        job_id = trackers.pull()[0]["id"]
        Crew(script={("intake", 1, "intake"): ("needs_human", self.QS)}).run_until_idle()
        self.assertEqual(trackers.check_answers(), [])          # our own question comment isn't an answer
        import time
        time.sleep(1.1)                                           # replies are compared by timestamp (seconds)
        LocalTracker({}, config.project()["name"]).comment(t["key"], "no, and admins only")
        trackers.pull()                                           # pull also checks for answers
        job = state.load(job_id)
        self.assertEqual((job["status"], job["stage"]), ("active", "intake"))
        self.assertEqual(job["answers"][0]["answer"], "no, and admins only")

    def test_needs_human_without_questions_is_a_plain_pause(self):
        make_repo("ask-none")
        add_ticket("Legal stuff")
        job_id = trackers.pull()[0]["id"]
        Crew(script={("intake", 1, "intake"): ("needs_human", {})}).run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "awaiting_human")
        self.assertNotIn("questions", job)
        with self.assertRaises(Exception):
            engine.answer(job_id, "whatever")


class SafeMergeTest(unittest.TestCase):
    def test_rebases_on_moved_main_and_regates_before_merging(self):
        repo = make_repo("moved", gate="test -f backend/hello.txt && test -f backend/other.txt")
        commit_on_main(repo, "backend/other.txt", "x\n", "seed other")
        add_ticket("Say hello")
        job_id = trackers.pull()[0]["id"]

        def land_other_work(t):
            if (t["stage"], t["attempt"]) == ("approve", 1):
                commit_on_main(repo, "backend/notes.txt", "merged meanwhile\n", "other ticket merged")

        Crew(on_task=land_other_work).run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        self.assertEqual(len(job["rebases"]), 1)
        # the merged branch contains the work that landed while it was in review
        self.assertEqual(git(repo, "show", "main:backend/notes.txt"), "merged meanwhile")
        self.assertEqual(git(repo, "show", "main:backend/hello.txt"), "attempt 1")
        merge_run = [h for h in job["history"] if h["stage"] == "merge"]
        self.assertEqual([h["status"] for h in merge_run], ["pass"])

    def test_conflict_with_moved_main_goes_back_to_builder(self):
        repo = make_repo("conflict")
        add_ticket("Say hello")
        job_id = trackers.pull()[0]["id"]

        def world(t):
            if (t["stage"], t["attempt"]) == ("approve", 1):
                commit_on_main(repo, "backend/hello.txt", "someone else's hello\n", "conflicting change")
            if (t["stage"], t["attempt"], t["agent"]) == ("build", 2, "backend-builder"):
                git(t["cwd"], "rebase", "-X", "theirs", "main")  # the builder resolves the conflict

        crew = Crew(on_task=world)
        crew.run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        merges = [h["status"] for h in job["history"] if h["stage"] == "merge"]
        self.assertEqual(merges, ["changes_requested", "pass"])
        brief2 = (state.briefs_dir(job_id) / "build.2.backend-builder.md").read_text()
        self.assertIn("merge conflict", brief2)
        self.assertIn("backend/hello.txt", brief2)
        self.assertEqual(git(repo, "show", "main:backend/hello.txt"), "attempt 2")

    def test_rebase_can_be_turned_off(self):
        repo = make_repo("norebase", policy={"auto_merge_max_risk": "low", "protected_paths": [],
                                              "rebase_before_merge": False})
        add_ticket("Say hello")
        job_id = trackers.pull()[0]["id"]

        def land(t):
            if (t["stage"], t["attempt"]) == ("approve", 1):
                commit_on_main(repo, "backend/notes.txt", "meanwhile\n", "other")

        Crew(on_task=land).run_until_idle()
        job = state.load(job_id)
        self.assertEqual(job["status"], "complete", job.get("status_reason"))
        self.assertNotIn("rebases", job)

    def test_github_workspace_branches_from_fresh_remote_not_stale_local_main(self):
        repo = make_repo("stale")
        origin = repo.parent / "stale-origin.git"
        git(repo.parent, "clone", "-q", "--bare", str(repo), str(origin))
        git(repo, "remote", "add", "origin", str(origin))
        git(repo, "fetch", "-q", "origin")
        # another machine merges to origin/main; the local main checkout never pulls
        other = repo.parent / "stale-other"
        git(repo.parent, "clone", "-q", str(origin), str(other))
        git(other, "config", "user.email", "o@test")
        git(other, "config", "user.name", "o")
        commit_on_main(other, "backend/merged.txt", "from PR #1\n", "PR #1")
        git(other, "push", "-q", "origin", "main")

        cfg_path = repo / ".factory" / "config.json"
        cfg = load_json(cfg_path)
        cfg["vcs"] = {**cfg.get("vcs", {}), "type": "github", "repo": "me/stale", "base_branch": "main"}
        from forgeline.util import write_json
        write_json(cfg_path, cfg)
        config.reload()

        job = {"id": "job-stale", "project": config.project()["name"]}
        status, summary, _ = scripts.workspace(job, {})
        self.assertEqual(status, "pass", summary)
        self.assertEqual(job["base_ref"], "origin/main")
        self.assertTrue((Path(job["worktree"]) / "backend" / "merged.txt").exists())
        self.assertFalse((repo / "backend" / "merged.txt").exists())  # local main still stale


if __name__ == "__main__":
    unittest.main()
