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


def _base_ref(job) -> str:
    """The latest base to branch from and rebase onto.

    github: fetch the remote base branch and use `origin/<base>`, so a job never starts from (or merges
    on top of) a stale local checkout. local: the local base branch is the source of truth.
    """
    proj = config.project(job["project"])
    vcfg = config.domain_config(proj)["vcs"]
    base = vcfg.get("base_branch", "main")
    if vcfg.get("type", "local") != "github":
        return base
    remote = vcfg.get("remote", "origin")
    proc = _git(proj["repo_path"], "fetch", "--quiet", remote, base, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git fetch {remote} {base} failed: {(proc.stderr or proc.stdout).strip()[:500]}")
    return f"{remote}/{base}"


def _job_base(job) -> str:
    return job.get("base_ref") or job.get("base_branch", "main")


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

    base_ref = _base_ref(job)
    if not wt.exists():
        exists = _git(repo, "rev-parse", "--verify", "--quiet", branch, check=False).returncode == 0
        if exists:
            _git(repo, "worktree", "add", str(wt), branch)
        else:
            _git(repo, "worktree", "add", "--no-track", "-b", branch, str(wt), base_ref)
    job["worktree"], job["branch"] = str(wt), branch
    job["base_branch"], job["base_ref"] = base, base_ref
    sha = _git(repo, "rev-parse", "--short", base_ref).stdout.strip()
    return "pass", f"worktree {wt} on {branch} from {base_ref} ({sha})", {"worktree": str(wt), "branch": branch}


def gate(job, sdef):
    """The deterministic gate: domain checks.sh must exit 0 on a clean, committed tree."""
    proj = config.project(job["project"])
    checks = config.domain_dir(proj) / "checks.sh"
    dirty = _git(job, "status", "--porcelain").stdout.strip()
    if dirty:
        return "fail", f"uncommitted changes in worktree (builders must commit):\n{dirty[:1500]}", {}
    base = _job_base(job)
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


def _rebase_on_latest(job, sdef, adapter):
    """Bring the job branch up to date with the latest base and re-run the gate on the new head.

    Returns None when the branch is current (or was rebased and is green), or a (status, summary, data)
    tuple that sends the job back to the builder: a conflict, or a gate that fails after the rebase.
    """
    base_ref = _base_ref(job)
    job["base_ref"] = base_ref
    if _git(job, "merge-base", "--is-ancestor", base_ref, "HEAD", check=False).returncode == 0:
        return None
    before = _git(job, "rev-parse", "--short", "HEAD").stdout.strip()
    proc = _git(job, "rebase", base_ref, check=False)
    if proc.returncode != 0:
        files = _git(job, "diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
        _git(job, "rebase", "--abort", check=False)
        return ("changes_requested",
                f"merge conflict: {base_ref} moved on since this job started, and the branch no longer "
                f"rebases cleanly. Conflicting files: {', '.join(files) or 'unknown'}.\n"
                f"Fix: in the worktree run `git rebase {base_ref}`, resolve each conflict so both your "
                f"change and the newer change on {base_ref} still work, `git add` the files, "
                f"`git rebase --continue`, and make sure the tests pass.",
                {"conflicts": files, "base_ref": base_ref})
    status, summary, _ = gate(job, sdef)
    if status != "pass":
        return ("changes_requested",
                f"rebased onto the latest {base_ref} cleanly, but the gate fails on the result. Something "
                f"merged since this job started interacts with this change.\n{summary}",
                {"base_ref": base_ref})
    adapter.update_branch(job)
    after = _git(job, "rev-parse", "--short", "HEAD").stdout.strip()
    job.setdefault("rebases", []).append({"from": before, "to": after, "onto": base_ref, "at": now()})
    return None


def merge(job, sdef):
    adapter = vcs.get(job)
    if policy.effective(job).get("rebase_before_merge", True):
        sent_back = _rebase_on_latest(job, sdef, adapter)
        if sent_back:
            return sent_back
    head = _git(job, "rev-parse", "HEAD").stdout.strip()
    changed = _git(job, "diff", "--name-only", f"{_job_base(job)}...HEAD").stdout.split()
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
