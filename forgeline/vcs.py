"""VCS adapters: where branches go and how merges happen.

local  : no remote. "PR" = the branch; merge = fast-forward the base branch locally.
github : push branch, gh pr create/reuse, gh pr merge. Uses whatever `gh` auth is active.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, state
from .util import FactoryError, run


def get(job: dict):
    proj = config.project(job["project"])
    cfg = config.domain_config(proj)["vcs"]
    kind = cfg.get("type", "local")
    if kind == "local":
        return LocalVcs(cfg, proj)
    if kind == "github":
        return GitHubVcs(cfg, proj)
    raise FactoryError(f"unknown vcs type: {kind}")


def _pr_body(job: dict) -> str:
    t = job["ticket"]
    spec = state.job_dir(job["id"]) / "spec.md"
    lines = [f"Closes {t['tracker']}:{t['key']} — {t['title']}", "", f"Factory job `{job['id']}`, risk `{job.get('risk')}`."]
    if spec.exists():
        lines += ["", "## Spec", spec.read_text()[:20000]]
    lines += ["", "🤖 Built by the software factory"]
    return "\n".join(lines)


class LocalVcs:
    def __init__(self, cfg, proj):
        self.cfg, self.repo = cfg, Path(proj["repo_path"])

    def open_pr(self, job):
        return {"number": None, "url": None, "ref": job["branch"]}

    def update_branch(self, job):
        pass  # the branch lives only in this repo

    def merge(self, job):
        base = job.get("base_branch", self.cfg.get("base_branch", "main"))
        cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo).stdout.strip()
        if cur != base:
            raise FactoryError(f"local merge needs {self.repo} checked out on {base} (is on {cur}); switch, then "
                               f"`forgeline human {job['id']} retry --stage merge`")
        if run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=self.repo).stdout.strip():
            raise FactoryError(f"local merge needs a clean {base} checkout in {self.repo}: commit or stash your "
                               f"changes, then `forgeline human {job['id']} retry --stage merge`")
        run(["git", "merge", "--no-ff", "-m", f"Merge {job['branch']} (factory {job['id']})", job["branch"]],
            cwd=self.repo)
        return run(["git", "rev-parse", "HEAD"], cwd=self.repo).stdout.strip()

    def comment(self, job, text):
        pass  # no PR to comment on; results are in the job history


class GitHubVcs:
    def __init__(self, cfg, proj):
        self.cfg, self.repo = cfg, Path(proj["repo_path"])
        self.gh_repo = cfg["repo"]

    def open_pr(self, job):
        wt = job["worktree"]
        self.update_branch(job)
        existing = json.loads(run(["gh", "pr", "list", "--repo", self.gh_repo, "--head", job["branch"],
                                   "--state", "open", "--json", "number,url"]).stdout)
        if existing:
            return {"number": existing[0]["number"], "url": existing[0]["url"], "ref": job["branch"]}
        run(["gh", "pr", "create", "--repo", self.gh_repo, "--base", job.get("base_branch", "main"),
             "--head", job["branch"], "--title", f"{job['ticket']['title']} [{job['ticket']['key']}]",
             "--body", _pr_body(job)] + (["--draft"] if self.cfg.get("draft") else []), cwd=wt)
        pr = json.loads(run(["gh", "pr", "view", job["branch"], "--repo", self.gh_repo,
                             "--json", "number,url"]).stdout)
        return {"number": pr["number"], "url": pr["url"], "ref": job["branch"]}

    def update_branch(self, job):
        # The job branch belongs to the factory; after a rebase it is rewritten. --force-with-lease only
        # overwrites the remote branch if nobody else pushed to it since our last push.
        run(["git", "push", "--force-with-lease", "-u", self.cfg.get("remote", "origin"), job["branch"]],
            cwd=job["worktree"])

    def merge(self, job):
        n = str(job["pr"]["number"])
        method = self.cfg.get("merge_method", "squash")
        run(["gh", "pr", "merge", n, "--repo", self.gh_repo, f"--{method}", "--delete-branch"])
        data = json.loads(run(["gh", "pr", "view", n, "--repo", self.gh_repo, "--json", "mergeCommit"]).stdout)
        return data["mergeCommit"]["oid"]

    def comment(self, job, text):
        if job.get("pr", {}).get("number"):
            run(["gh", "pr", "comment", str(job["pr"]["number"]), "--repo", self.gh_repo, "--body", text],
                check=False)
