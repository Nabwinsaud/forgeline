"""The deterministic pipeline engine.

Agents only produce results (status + summary + data). The engine alone decides
transitions, attempts, locks, and side effects. This is what makes the factory
resumable and auditable.
"""
from __future__ import annotations

import datetime as _dt

from . import compose, config, scripts, state, trackers
from .util import FactoryError, load_json, now, parse_time

VALID_STATUSES = {"pass", "fail", "changes_requested", "needs_human", "reject", "skip", "pending"}
# Worst outcome wins when several agents run in one stage.
PRECEDENCE = ["needs_human", "reject", "fail", "changes_requested", "pending", "pass"]

TRACKER_STATUS_ON_ENTER = {
    "workspace": "in_progress",
    "review": "in_review",
    "awaiting_human": "blocked",
    "blocked": "blocked",
}


# ---------------------------------------------------------------- definitions

def stage_def(stage_id: str) -> dict:
    for s in config.pipeline()["stages"]:
        if s["id"] == stage_id:
            return s
    raise FactoryError(f"unknown stage: {stage_id}")


def is_terminal(stage_id: str) -> bool:
    return stage_id in config.pipeline()["terminal"]


def agents_for(job: dict, sdef: dict) -> list[dict]:
    """Resolve which agents run for this job in this stage (area filters + domain reviewers)."""
    proj = config.project(job["project"])
    dcfg = config.domain_config(proj)
    areas = set(job.get("areas") or dcfg["areas"].keys())
    out = []
    for a in sdef.get("agents", []):
        a = {"name": a} if isinstance(a, str) else dict(a)
        when = a.get("when")
        if when and when.startswith("area:") and when[5:] not in areas:
            continue
        out.append(a)
    if sdef.get("include_domain_reviewers"):
        for r in dcfg.get("domain_reviewers", []):
            out.append({"name": f"domain-{r['name']}", "domain": r})
    return out


def max_attempts(sdef: dict) -> int:
    return sdef.get("max_attempts", config.factory_config().get("default_max_attempts", 3))


# ---------------------------------------------------------------- dispatch

def _lock_stale(lock: dict) -> bool:
    timeout = config.factory_config().get("lock_timeout_minutes", 90)
    age = _dt.datetime.now(_dt.timezone.utc) - parse_time(lock["at"])
    return age > _dt.timedelta(minutes=timeout)


def _missing_agents(job: dict, lock: dict) -> list[dict]:
    return [a for a in lock["agents"]
            if not state.result_path(job["id"], lock["stage"], lock["attempt"], a["name"]).exists()]


def dispatch(limit: int | None = None) -> list[dict]:
    """Advance every active job as far as scripts allow, then hand out agent tasks.

    Returns a list of task dicts for the orchestrator to run as subagents.
    """
    cfg = config.factory_config()
    limit = limit or cfg.get("concurrency", 3)
    tasks: list[dict] = []
    in_flight = 0

    for job in state.all_jobs():
        if job["status"] != "active":
            continue
        lock = job.get("lock")
        if lock:
            missing = _missing_agents(job, lock)
            if not missing:
                complete(job["id"])  # results landed while we were away
                job = state.load(job["id"])
            elif _lock_stale(lock):
                tasks.extend(_tasks(job, lock, missing))  # re-hand-out only what is missing
                job["lock"]["at"] = now()
                state.save(job)
                in_flight += 1
                continue
            else:
                in_flight += 1
                continue

        job = _run_scripts(job)
        if job["status"] != "active" or job.get("lock") or in_flight >= limit:
            if job.get("lock"):
                in_flight += 1
            continue

        sdef = stage_def(job["stage"])
        if sdef["kind"] == "script":
            continue  # pending script (e.g. waiting for deploy); try again next tick
        lock = _claim(job, sdef)
        if lock:
            tasks.extend(_tasks(job, lock, lock["agents"]))
            in_flight += 1
    return tasks


def _claim(job: dict, sdef: dict) -> dict | None:
    stage = sdef["id"]
    attempt = job["attempts"].get(stage, 0) + 1
    if attempt > max_attempts(sdef):
        _transition(job, stage, "blocked", f"{stage} exceeded max attempts ({max_attempts(sdef)})")
        state.save(job)
        return None
    agents = agents_for(job, sdef)
    if not agents:
        # nothing applies (e.g. no frontend) -> treat as pass
        job["attempts"][stage] = attempt
        _record(job, stage, attempt, "skip", "no agents apply", {})
        _transition(job, stage, sdef["on"].get("pass", "blocked"), "no agents apply")
        state.save(job)
        return None
    job["attempts"][stage] = attempt
    job["lock"] = {"stage": stage, "attempt": attempt, "agents": agents, "at": now(), "started_at": now()}
    state.save(job)
    return job["lock"]


def _tasks(job: dict, lock: dict, agents: list[dict]) -> list[dict]:
    sdef = stage_def(lock["stage"])
    out = []
    for a in agents:
        brief = compose.brief(job, sdef, a, lock["attempt"])
        out.append({
            "job": job["id"],
            "stage": lock["stage"],
            "attempt": lock["attempt"],
            "agent": a["name"],
            "model": a.get("domain", {}).get("model") or config.model_for(a["name"]),
            "parallel": sdef.get("parallel", False),
            "brief_path": str(brief),
            "result_path": str(state.result_path(job["id"], lock["stage"], lock["attempt"], a["name"])),
            "cwd": job.get("worktree") or config.project(job["project"])["repo_path"],
        })
    return out


# ---------------------------------------------------------------- scripts

def _run_scripts(job: dict) -> dict:
    """Run consecutive script stages until an agent stage, terminal, or pending."""
    for _ in range(20):
        if job["status"] != "active" or is_terminal(job["stage"]):
            return job
        sdef = stage_def(job["stage"])
        if sdef["kind"] != "script":
            return job
        stage = sdef["id"]
        attempt = job["attempts"].get(stage, 0) + 1
        if attempt > max_attempts(sdef):
            _transition(job, stage, "blocked", f"{stage} exceeded max attempts")
            state.save(job)
            return job
        started = now()
        try:
            status, summary, data = scripts.run(sdef["run"], job, sdef)
        except Exception as exc:  # script crashed: record and block, never loop silently
            status, summary, data = "fail", f"script error: {exc}", {}
        if status == "pending":
            job["last_poll"] = {"stage": stage, "at": now(), "summary": summary}
            state.save(job)
            return job
        job["attempts"][stage] = attempt
        _record(job, stage, attempt, status, summary, data, started)
        _transition(job, stage, sdef["on"].get(status, "blocked"), summary)
        state.save(job)
    return job


# ---------------------------------------------------------------- completion

def complete(job_id: str) -> dict:
    job = state.load(job_id)
    lock = job.get("lock")
    if not lock:
        raise FactoryError(f"{job_id} has no stage in flight")
    missing = _missing_agents(job, lock)
    if missing:
        raise FactoryError(f"{job_id}: waiting on results from {[a['name'] for a in missing]}")

    results = []
    for a in lock["agents"]:
        r = load_json(state.result_path(job_id, lock["stage"], lock["attempt"], a["name"]))
        st = r.get("status")
        if st not in VALID_STATUSES:
            r = {"status": "fail", "summary": f"invalid status {st!r} from {a['name']}", "raw": r}
        r["agent"] = a["name"]
        results.append(r)

    statuses = ["pass" if r["status"] == "skip" else r["status"] for r in results]
    status = next(s for s in PRECEDENCE if s in statuses)
    summary = " | ".join(f"{r['agent']}: {r.get('summary', '')}"[:300] for r in results)
    usage = _sum_usage(results)

    _apply_side_effects(job, lock["stage"], results)
    if lock["stage"] in ("review", "approve") and job.get("pr"):
        try:
            from . import vcs
            head = "LGTM ✅" if lock["stage"] == "approve" and status == "pass" else f"{lock['stage']}: {status}"
            vcs.get(job).comment(job, f"**Factory {head}**\n\n" + "\n".join(
                f"- **{r['agent']}** `{r['status']}` — {r.get('summary', '')}" for r in results))
        except Exception as exc:
            job.setdefault("warnings", []).append(f"pr comment failed: {exc}")
    _record(job, lock["stage"], lock["attempt"], status, summary, {"usage": usage}, lock.get("started_at"))
    job["lock"] = None
    sdef = stage_def(lock["stage"])
    _transition(job, lock["stage"], sdef["on"].get(status, "blocked"), summary)
    state.save(job)
    return job


def _apply_side_effects(job: dict, stage: str, results: list[dict]) -> None:
    for r in results:
        data = r.get("data", {}) or {}
        if stage == "intake":
            job["risk"] = data.get("risk", job["risk"])
            job["size"] = data.get("size", job["size"])
            if data.get("areas"):
                job["areas"] = data["areas"]
        if stage == "spec" and data.get("areas"):
            job["areas"] = data["areas"]
        if stage == "spec" and data.get("risk"):
            job["risk"] = data["risk"]  # spec writer may raise risk after deeper look


def _sum_usage(results: list[dict]) -> dict:
    total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for r in results:
        for k in total:
            total[k] += (r.get("usage") or {}).get(k, 0) or 0
    return total


def _record(job, stage, attempt, status, summary, data, started_at=None) -> None:
    job["history"].append({
        "stage": stage, "attempt": attempt, "status": status,
        "summary": (summary or "")[:2000], "data": data,
        "started_at": started_at or now(), "finished_at": now(),
    })


def _transition(job: dict, from_stage: str, to: str, reason: str) -> None:
    if to in ("blocked", "awaiting_human", "rejected", "complete"):
        job["status"] = to
        job["paused_stage"] = from_stage
        job["status_reason"] = (reason or "")[:2000]
    job["stage"] = to
    trackers.on_enter(job, to, reason)


# ---------------------------------------------------------------- humans

def human(job_id: str, decision: str, stage: str | None = None, note: str = "") -> dict:
    job = state.load(job_id)
    if job["status"] not in ("awaiting_human", "blocked"):
        raise FactoryError(f"{job_id} is {job['status']}, not waiting on a human")
    paused = job.get("paused_stage")
    _record(job, "human", 0, decision, note or decision, {"by": "human"})
    if decision == "approve":
        if paused == "merge":
            job["human_merge_approved"] = True  # policy override, recorded in history
            nxt = "merge"
        else:
            nxt = stage_def(paused)["on"].get("pass", paused)
        job.update(status="active", stage=nxt, lock=None)
    elif decision == "reject":
        job.update(status="rejected", stage="rejected", lock=None)
    elif decision == "retry":
        target = stage or paused
        job["attempts"][target] = 0
        job.update(status="active", stage=target, lock=None)
    else:
        raise FactoryError("decision must be approve | reject | retry")
    trackers.on_enter(job, job["stage"], f"human {decision}: {note}")
    state.save(job)
    return job
