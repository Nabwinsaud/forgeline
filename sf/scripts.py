"""Deterministic script stages. Each returns (status, summary, data)."""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from . import config, envs, policy, trackers, vcs
from .util import now, parse_time
from .util import run as sh


def run(name: str, job: dict, sdef: dict):
    return {
        "workspace": workspace,
        "gate": gate,
        "open_pr": open_pr,
        "merge": merge,
        "wait_deploy": wait_deploy,
        "close_ticket": close_ticket,
    }[name](job, sdef)



def _git(job_or_path, *args, check=True):
    cwd = job_or_path if isinstance(job_or_path, (str, Path)) else job_or_path["worktree"]
    return sh(["git", *args], cwd=cwd, check=check)


def workspace(job, sdef):
    """Isolated git worktree per job so jobs can run in parallel without stepping on each other."""
    proj = config.project(job["project"])
    repo = Path(proj["repo_path"])
    base = config.domain_config(proj)["vcs"].get("base_branch", "main")
    branch = f"factory/{job['id']}"
    wt = repo / ".factory" / "worktrees" / job["id"]

    exclude = repo / ".git" / "info" / "exclude"
    if exclude.exists() and ".factory/worktrees/" not in exclude.read_text():
        with exclude.open("a") as f:
            f.write("\n.factory/worktrees/\n")

    if not wt.exists():
        exists = _git(repo, "rev-parse", "--verify", "--quiet", branch, check=False).returncode == 0
        if exists:
            _git(repo, "worktree", "add", str(wt), branch)
        else:
            _git(repo, "worktree", "add", "-b", branch, str(wt), base)
    job["worktree"], job["branch"] = str(wt), branch
    job["base_branch"] = base
    return "pass", f"worktree {wt} on {branch} from {base}", {"worktree": str(wt), "branch": branch}


def gate(job, sdef):
    """The deterministic gate: domain checks.sh must exit 0 on a clean, committed tree."""
    proj = config.project(job["project"])
    checks = config.domain_dir(proj) / "checks.sh"
    dirty = _git(job, "status", "--porcelain").stdout.strip()
    if dirty:
        return "fail", f"uncommitted changes in worktree (builders must commit):\n{dirty[:1500]}", {}
    base = job.get("base_branch", "main")
    if not _git(job, "diff", "--name-only", f"{base}...HEAD").stdout.strip():
        return "fail", "no changes vs base branch", {}
    if not checks.exists():
        return "fail", f"missing deterministic gate: {checks}", {}
    proc = sh(["bash", str(checks)], cwd=job["worktree"], check=False, timeout=3600,
              env={"FACTORY_BASE": base, "FACTORY_AREAS": ",".join(job.get("areas") or []),
                   "FACTORY_JOB": job["id"]})
    head = _git(job, "rev-parse", "HEAD").stdout.strip()
    tail = (proc.stdout + "\n" + proc.stderr)[-6000:]
    if proc.returncode != 0:
        return "fail", f"checks.sh exited {proc.returncode}\n{tail}", {"sha": head}
    job["gate_sha"] = head
    return "pass", f"checks.sh green on {head[:10]}", {"sha": head}


def open_pr(job, sdef):
    pr = vcs.get(job).open_pr(job)
    job["pr"] = pr
    return "pass", f"PR ready: {pr.get('url') or pr.get('ref')}", pr


def merge(job, sdef):
    adapter = vcs.get(job)
    head = _git(job, "rev-parse", "HEAD").stdout.strip()
    changed = _git(job, "diff", "--name-only", f"{job.get('base_branch', 'main')}...HEAD").stdout.split()
    status, reason = policy.merge_decision(job, head, changed)
    if status != "pass":
        return status, reason, {"head": head}
    sha = adapter.merge(job)
    job["merge_sha"] = sha
    return "pass", f"merged at {sha[:10]} ({reason})", {"merge_sha": sha}


def wait_deploy(job, sdef):
    env_name = sdef["env"]
    proj = config.project(job["project"])
    env_cfg = config.domain_config(proj)["envs"].get(env_name, {"type": "none"})
    key = f"deploy_wait_{env_name}"
    job.setdefault(key, now())
    status, summary = envs.get(env_cfg).check(job, env_cfg)
    if status == "pending":
        limit = env_cfg.get("timeout_minutes", 45)
        if _dt.datetime.now(_dt.timezone.utc) - parse_time(job[key]) > _dt.timedelta(minutes=limit):
            return "fail", f"{env_name} deploy not seen after {limit} min: {summary}", {}
    return status, summary, {"env": env_name}


def close_ticket(job, sdef):
    trackers.get_for(job).set_status(job["ticket"]["key"], "done")
    trackers.get_for(job).comment(job["ticket"]["key"], _final_report(job))
    proj = config.project(job["project"])
    if job.get("worktree") and os.path.exists(job["worktree"]):
        sh(["git", "worktree", "remove", "--force", job["worktree"]], cwd=proj["repo_path"], check=False)
    return "pass", "ticket closed", {}


def _final_report(job) -> str:
    lines = [f"Software factory finished `{job['id']}`."]
    if job.get("pr"):
        lines.append(f"PR: {job['pr'].get('url') or job['pr'].get('ref')}")
    if job.get("merge_sha"):
        lines.append(f"Merged: {job['merge_sha'][:10]}")
    for h in job["history"]:
        lines.append(f"- {h['stage']}#{h['attempt']}: {h['status']}")
    return "\n".join(lines)
