"""`forgeline init` stack detection and guard hook behaviour."""
import json
import os
import subprocess
import unittest

from helpers import ROOT, TMP, git

from forgeline import init

GUARD = ROOT / "hooks" / "guard.py"


def guard(mode, payload, env=None):
    return subprocess.run(["python3", str(GUARD), mode], input=json.dumps(payload), text=True,
                          capture_output=True, env={**os.environ, **(env or {})})


class InitTest(unittest.TestCase):
    def test_detects_go_backend_and_vite_frontend(self):
        repo = TMP / "fullstack"
        (repo / "backend").mkdir(parents=True)
        (repo / "frontend").mkdir()
        (repo / "backend" / "go.mod").write_text("module x\n")
        (repo / "frontend" / "package.json").write_text('{"scripts":{"test":"vitest","build":"vite build"}}')
        (repo / "frontend" / "vite.config.ts").write_text("")
        git(repo, "init", "-q", "-b", "main")
        comps = init.detect(repo)
        self.assertIn({"dir": "backend", "lang": "go", "area": "backend"}, comps)
        self.assertIn({"dir": "frontend", "lang": "node", "area": "frontend"}, comps)
        checks = init.render_checks(comps)
        self.assertIn('pushd "backend"', checks)
        self.assertIn("go vet ./...", checks)
        self.assertIn('pushd "frontend"', checks)
        self.assertIn("tsc --noEmit", checks)

    def test_root_level_python_service(self):
        repo = TMP / "pysvc"
        repo.mkdir()
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        self.assertEqual(init.detect(repo), [{"dir": ".", "lang": "python", "area": "backend"}])

    def test_init_writes_harness_and_rules(self):
        repo = TMP / "initme"
        (repo / "api").mkdir(parents=True)
        (repo / "api" / "go.mod").write_text("module x\n")
        git(repo, "init", "-q", "-b", "trunk")
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            os.environ.pop("FORGELINE_REPO", None)
            res = init.run(rules="auto")
        finally:
            os.chdir(cwd)
        self.assertEqual(res["base_branch"], "trunk")
        self.assertEqual(res["rules"], ["common", "go"])
        for f in ("config.json", "checks.sh", "domain.md", ".gitignore"):
            self.assertTrue((repo / ".factory" / f).exists(), f)
        self.assertTrue((repo / ".claude" / "rules" / "forgeline" / "go").is_dir())
        cfg = json.loads((repo / ".factory" / "config.json").read_text())
        self.assertEqual(cfg["policy"]["auto_merge_max_risk"], "none")  # safe by default
        self.assertEqual(cfg["areas"], {"backend": ["api/"]})


class GuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = TMP / "guarded"
        (cls.repo / ".factory").mkdir(parents=True)
        (cls.repo / ".factory" / "config.json").write_text('{"vcs":{"base_branch":"main"}}')
        cls.wt = cls.repo / ".factory" / "worktrees" / "job-1"
        (cls.wt / ".factory").mkdir(parents=True)
        (cls.wt / ".factory" / "config.json").write_text("{}")

    def bash(self, cmd, cwd=None, agent_type=None):
        payload = {"cwd": str(cwd or self.repo), "tool_name": "Bash", "tool_input": {"command": cmd}}
        if agent_type:
            payload["agent_type"] = agent_type
        return guard("pre-bash", payload)

    def write(self, path, content="x", cwd=None, env=None):
        return guard("pre-write", {"cwd": str(cwd or self.repo), "tool_name": "Write",
                                   "tool_input": {"file_path": str(path), "content": content}}, env)

    def test_force_push_always_blocked(self):
        self.assertEqual(self.bash("git push --force origin feature").returncode, 2)

    def test_push_to_main_blocked_for_agents_only(self):
        self.assertEqual(self.bash("git push origin main", cwd=self.wt).returncode, 2)
        self.assertEqual(self.bash("git push origin main", agent_type="forgeline:backend-builder").returncode, 2)
        self.assertEqual(self.bash("git push origin main").returncode, 0)  # a human driving Claude

    def test_agent_cannot_merge_or_touch_tickets(self):
        self.assertEqual(self.bash("gh pr merge 12 --squash", cwd=self.wt).returncode, 2)
        self.assertEqual(self.bash("gh issue close 4", cwd=self.wt).returncode, 2)

    def test_agent_cannot_edit_gate_or_config(self):
        r = self.write(self.wt / ".factory" / "checks.sh", "exit 0", cwd=self.wt)
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot edit the gate", r.stderr)
        for cmd in ("echo 'exit 0' > .factory/checks.sh", "cp /tmp/x .factory/checks.sh",
                    "sed -i '' s/a/b/ .factory/config.json", "rm -f .factory/pipeline.json"):
            self.assertEqual(self.bash(cmd, cwd=self.wt).returncode, 2, cmd)
        self.assertEqual(self.bash("cat .factory/checks.sh", cwd=self.wt).returncode, 0)

    def test_generated_code_protected(self):
        gen = self.repo / "models.sql.go"
        gen.write_text("// Code generated by sqlc. DO NOT EDIT.\npackage db\n")
        self.assertEqual(self.write(gen, "package db").returncode, 2)

    def test_secrets_blocked(self):
        self.assertEqual(self.write(self.repo / "a.go", 'k := "AKIAABCDEFGHIJKLMNOP"').returncode, 2)
        self.assertEqual(self.write(self.repo / "b.go", "ok := 1").returncode, 0)

    def test_strict_profile_extras(self):
        r = self.write(self.repo / ".env", "A=1", env={"FORGELINE_HOOK_PROFILE": "strict"})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.write(self.repo / ".env", "A=1").returncode, 0)

    def test_inactive_outside_factory_repos(self):
        other = TMP / "plain"
        other.mkdir(exist_ok=True)
        r = guard("pre-bash", {"cwd": str(other), "tool_input": {"command": "git push --force origin x"}})
        self.assertEqual(r.returncode, 0)

    def test_session_start_briefing(self):
        r = guard("session-start", {"cwd": str(self.repo)})
        self.assertIn("Forgeline is active", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
