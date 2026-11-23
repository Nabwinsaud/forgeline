"""Durable job store. One directory per job under ..factory/state/jobs/<id>/.

job.json          current state (stage, status, attempts, lock, history)
briefs/*.md       composed prompts handed to agents
results/*.json    agent / script outputs, one file per stage attempt + agent
"""
from __future__ import annotations

from pathlib import Path

from . import config
from .util import FactoryError, load_json, now, slugify, write_json


def jobs_dir() -> Path:
    return config.state_dir() / "jobs"


def job_dir(job_id: str) -> Path:
    return jobs_dir() / job_id


def results_dir(job_id: str) -> Path:
    return job_dir(job_id) / "results"


def briefs_dir(job_id: str) -> Path:
    return job_dir(job_id) / "briefs"


def load(job_id: str) -> dict:
    path = job_dir(job_id) / "job.json"
    if not path.exists():
        raise FactoryError(f"unknown job: {job_id}")
    return load_json(path)


def save(job: dict) -> None:
    job["updated_at"] = now()
    write_json(job_dir(job["id"]) / "job.json", job)


def all_jobs() -> list[dict]:
    if not jobs_dir().exists():
        return []
    jobs = []
    for d in sorted(jobs_dir().iterdir()):
        if (d / "job.json").exists():
            jobs.append(load_json(d / "job.json"))
    return jobs


def find_by_ticket(project: str, tracker: str, key: str) -> dict | None:
    for j in all_jobs():
        t = j["ticket"]
        if j["project"] == project and t["tracker"] == tracker and t["key"] == key:
            return j
    return None


def create(project: str, ticket: dict, start_stage: str) -> dict:
    existing = find_by_ticket(project, ticket["tracker"], ticket["key"])
    if existing:
        return existing
    job_id = slugify(f"{ticket['tracker']}-{ticket['key']}", 40)
    job = {
        "id": job_id,
        "project": project,
        "ticket": ticket,
        "stage": start_stage,
        "status": "active",
        "attempts": {},
        "risk": None,
        "size": None,
        "areas": [],
        "branch": None,
        "worktree": None,
        "pr": None,
        "gate_sha": None,
        "merge_sha": None,
        "lock": None,
        "history": [],
        "created_at": now(),
        "updated_at": now(),
    }
    save(job)
    return job


def result_path(job_id: str, stage: str, attempt: int, agent: str) -> Path:
    return results_dir(job_id) / f"{stage}.{attempt}.{agent}.json"


def latest_results(job: dict, stage: str) -> list[dict]:
    """Results from the most recent attempt of a stage (used to feed back into the next attempt)."""
    attempt = job["attempts"].get(stage, 0)
    if attempt == 0:
        return []
    out = []
    for p in sorted(results_dir(job["id"]).glob(f"{stage}.{attempt}.*.json")):
        data = load_json(p)
        data.setdefault("agent", p.stem.split(".", 2)[2])
        out.append(data)
    return out
