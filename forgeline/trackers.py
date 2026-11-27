"""Tracker adapter registry + pipeline hooks.

Every tracker implements the same four calls, so GitHub Issues, Jira, Linear,
or anything else is a new file in forgeline/adapters/, not a pipeline change.

Logical statuses the factory uses: ready, in_progress, in_review, blocked, done.
Each domain maps them to real tracker states in .factory/config.json -> tracker.status_map.
"""
from __future__ import annotations

from . import config, state


def get(tracker_cfg: dict, project_name: str):
    kind = tracker_cfg.get("type", "local")
    if kind == "local":
        from .adapters.tracker_local import LocalTracker as T
    elif kind == "github":
        from .adapters.tracker_github import GitHubTracker as T
    elif kind == "jira":
        from .adapters.tracker_jira import JiraTracker as T
    elif kind == "linear":
        from .adapters.tracker_linear import LinearTracker as T
    else:
        raise ValueError(f"unknown tracker type: {kind}")
    return T(tracker_cfg, project_name)


def get_for(job: dict):
    proj = config.project(job["project"])
    cfg = config.domain_config(proj)["tracker"]
    if job["ticket"].get("tracker") == "local" and cfg.get("type", "local") != "local":
        cfg = {"type": "local"}  # a `forgeline do` job lives in the local tracker, whatever the repo uses
    return get(cfg, job["project"])


def do(title: str, body: str = "") -> dict:
    """Start a job from one sentence: a local ticket, enqueued now. No tracker setup needed."""
    from .adapters.tracker_local import LocalTracker
    proj = config.project()
    t = LocalTracker({}, proj["name"]).add(title, body, status="in_progress")
    ticket = {"tracker": "local", "key": t["key"], "title": t["title"], "body": t["body"],
              "url": str(config.domain_dir() / "tickets" / f"{t['key']}.json")}
    return state.create(proj["name"], ticket, config.pipeline()["start"])


def pull(project_name: str | None = None) -> list[dict]:
    """Fetch ready tickets from this repo's tracker and enqueue them as jobs."""
    proj = config.project()
    project_name = proj["name"]
    tracker = get(config.domain_config(proj)["tracker"], project_name)
    start = config.pipeline()["start"]
    check_answers(project_name)
    created = []
    for ticket in tracker.list_ready():
        if state.find_by_ticket(project_name, ticket["tracker"], ticket["key"]):
            continue
        created.append(state.create(project_name, ticket, start))
    return created


def on_enter(job: dict, stage: str, reason: str) -> None:
    """Best-effort tracker sync. Never fails the pipeline; errors land in job history."""
    from .engine import TRACKER_STATUS_ON_ENTER
    logical = TRACKER_STATUS_ON_ENTER.get(stage)
    if not logical:
        return
    try:
        t = get_for(job)
        t.set_status(job["ticket"]["key"], logical)
        if logical == "in_review" and job.get("pr"):
            t.comment(job["ticket"]["key"], f"Factory opened PR: {job['pr'].get('url') or job['pr'].get('ref')}")
        q = job.get("questions") or {}
        if logical == "blocked" and q.get("open") and not q.get("posted"):
            t.comment(job["ticket"]["key"], questions_comment(job))
            q["posted"] = True
        elif logical == "blocked":
            t.comment(job["ticket"]["key"], f"Factory paused at `{job.get('paused_stage')}` ({stage}): {reason[:1500]}")
    except Exception as exc:  # tracker outages must not break the factory
        job.setdefault("warnings", []).append(f"tracker sync failed on {stage}: {exc}")


FACTORY_PREFIXES = ("Factory ", "Software factory", "Forgeline ")


def questions_comment(job: dict) -> str:
    q = job["questions"]
    lines = ["Forgeline has a few questions before building this:", ""]
    lines += [f"{i}. {item}" for i, item in enumerate(q["items"], 1)]
    lines += ["", "Reply here and the job picks up where it stopped. "
              f"(Or from a terminal: forgeline answer {job['id']} \"...\")"]
    return "\n".join(lines)


def check_answers(project_name: str | None = None) -> list[dict]:
    """Resume jobs whose open questions got a reply on the ticket since they were asked."""
    from . import engine
    from .util import parse_time
    resumed = []
    for job in state.all_jobs():
        q = job.get("questions") or {}
        if job.get("status") != "awaiting_human" or not q.get("open"):
            continue
        if project_name and job["project"] != project_name:
            continue
        try:
            tracker = get_for(job)
            if not hasattr(tracker, "comments"):
                continue
            asked = parse_time(q["asked_at"])
            replies = [c for c in tracker.comments(job["ticket"]["key"])
                       if parse_time(c["at"]) > asked and c.get("text", "").strip()
                       and not c["text"].lstrip().startswith(FACTORY_PREFIXES)]
        except Exception as exc:  # a tracker hiccup just means we look again next time
            job.setdefault("warnings", []).append(f"checking answers failed: {exc}")
            state.save(job)
            continue
        if replies:
            text = "\n\n".join(c["text"].strip() for c in replies)
            by = replies[-1].get("author") or "ticket"
            resumed.append(engine.answer(job["id"], text, by=by))
    return resumed
