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


class PackTest(unittest.TestCase):
    def test_add_update_remove_pack_and_its_gate_check(self):
        from helpers import make_repo
        from forgeline import config, packs
        from forgeline.util import load_json
        repo = make_repo("packs", gate="step() { echo \"==> $*\"; }\n# --- Your business checks go here\nprintf '\\ngate: all checks passed\\n'")
        names = {p["name"] for p in packs.available()}
        self.assertTrue({"money", "auth", "api", "web-app"} <= names)

        res = packs.add("money")
        self.assertIn("checks.sh", res["changed"])
        packs.add("money")  # re-adding updates in place, never duplicates
        domain = (repo / ".factory" / "domain.md").read_text()
        checks = (repo / ".factory" / "checks.sh").read_text()
        self.assertEqual(domain.count("<!-- pack:money -->"), 1)
        self.assertEqual(checks.count("# >>> pack:money"), 1)
        self.assertLess(checks.index("# >>> pack:money"), checks.index("# --- Your business checks go here"))
        revs = load_json(repo / ".factory" / "config.json")["domain_reviewers"]
        self.assertEqual([r["name"] for r in revs if r.get("pack") == "money"], ["money-rules"])
        self.assertEqual(config.validate(), [])
        self.assertEqual(packs.installed(), ["money"])

        # the money check judges only lines the branch adds
        git(repo, "add", "-A"); git(repo, "commit", "-qm", "pack")
        git(repo, "checkout", "-qb", "feature")
        (repo / "price.py").write_text("def total(items):\n    price = float(items[0])  # bad\n")
        git(repo, "add", "-A"); git(repo, "commit", "-qm", "float money")
        env = {**os.environ, "FACTORY_BASE": "main", "PATH": "/usr/bin:/bin"}
        bad = subprocess.run(["bash", ".factory/checks.sh"], cwd=repo, capture_output=True, text=True, env=env)
        self.assertNotEqual(bad.returncode, 0, bad.stdout)
        self.assertIn("floating point", bad.stdout)
        (repo / "price.py").write_text("def total(items):\n    price_cents = int(items[0])\n")
        git(repo, "add", "-A"); git(repo, "commit", "-qm", "fix")
        good = subprocess.run(["bash", ".factory/checks.sh"], cwd=repo, capture_output=True, text=True, env=env)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        git(repo, "checkout", "-q", "main")

        changed = packs.remove("money")
        self.assertIn("reviewers/money-rules.md", changed)
        self.assertNotIn("pack:money", (repo / ".factory" / "checks.sh").read_text())
        self.assertNotIn("pack:money", (repo / ".factory" / "domain.md").read_text())
        self.assertFalse((repo / ".factory" / "reviewers" / "money-rules.md").exists())

    def test_pack_from_a_folder(self):
        from helpers import make_repo
        from forgeline import packs
        repo = make_repo("packs-folder")
        src = TMP / "my-pack"
        src.mkdir()
        (src / "pack.json").write_text('{"name": "Clinic", "description": "patient data"}')
        (src / "domain.md").write_text("- Patient records never leave the EU region.\n")
        res = packs.add(str(src))
        self.assertEqual(res["pack"], "clinic")
        self.assertIn("never leave the EU", (repo / ".factory" / "domain.md").read_text())


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

    def test_monorepo_apps_and_more_languages(self):
        repo = TMP / "mono"
        for d, f, body in (("apps/web", "package.json", '{"dependencies":{"react":"19"},"scripts":{"test":"vitest","lint":"eslint ."}}'),
                           ("apps/api", "Cargo.toml", "[package]\nname='api'\n"),
                           ("services/billing", "pom.xml", "<project/>"),
                           ("services/mailer", "Gemfile", "source 'https://rubygems.org'\n")):
            (repo / d).mkdir(parents=True)
            (repo / d / f).write_text(body)
        (repo / "apps" / "web" / "pnpm-lock.yaml").write_text("")
        comps = init.detect(repo)
        self.assertIn({"dir": "apps/web", "lang": "node", "area": "frontend"}, comps)  # react dep => frontend
        self.assertIn({"dir": "apps/api", "lang": "rust", "area": "backend"}, comps)
        self.assertIn({"dir": "services/billing", "lang": "java", "area": "backend"}, comps)
        self.assertIn({"dir": "services/mailer", "lang": "ruby", "area": "backend"}, comps)
        checks = init.render_checks(comps)
        self.assertIn("cargo test --all", checks)
        self.assertIn("mvn -B verify", checks)
        self.assertIn("bundle exec rspec", checks)
        for c in comps:
            c["_abs"] = str(repo / c["dir"])
        cmds = init._commands(comps)
        self.assertEqual(cmds["frontend_test"], "cd apps/web && pnpm test")
        self.assertEqual(cmds["frontend_lint"], "cd apps/web && pnpm run lint")
        self.assertNotIn("frontend_build", cmds)  # no build script, no made-up command

    def test_makefile_fallback_and_ci_hints(self):
        repo = TMP / "makeonly"
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / "Makefile").write_text("lint:\n\tshellcheck *.sh\ntest:\n\tbats tests\n")
        (repo / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n  t:\n    steps:\n      - run: make test\n      - run: echo hi\n      - name: x\n        run: shellcheck --check-sourced *.sh\n")
        comps = init.detect(repo)
        self.assertEqual(comps, [{"dir": ".", "lang": "make", "area": "backend", "targets": ["lint", "test"]}])
        hints = init.ci_commands(repo)
        self.assertEqual(hints, ["make test", "shellcheck --check-sourced *.sh"])
        checks = init.render_checks(comps, hints)
        self.assertIn("make lint test", checks)
        self.assertIn("# make test", checks)

    def test_greenfield_gate_passes_then_checks_only_picks_up_the_stack(self):
        repo = TMP / "greenfield"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        (repo / "README.md").write_text("# new thing\n")
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            os.environ.pop("FORGELINE_REPO", None)
            init.run(rules="none")
            gate = subprocess.run(["bash", ".factory/checks.sh"], capture_output=True, text=True,
                                  env={**os.environ, "PATH": "/usr/bin:/bin"})
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            (repo / "go.mod").write_text("module x\n")
            res = init.refresh_checks()
            self.assertEqual(res["components"], [{"dir": ".", "lang": "go", "area": "backend"}])
            self.assertIn("go test", (repo / ".factory" / "checks.sh").read_text())
            self.assertIn("backend_test", res["commands"])
        finally:
            os.chdir(cwd)

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
