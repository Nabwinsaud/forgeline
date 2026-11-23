"""bin/factory — the only interface the orchestrator (Claude, Codex, CI, a human) needs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import config, engine, state, trackers
from .util import CONFIG_PATH, FACTORY_DIR, FACTORY_ROOT, STATE_DIR, FactoryError, load_json, parse_time, write_json


def cmd_init(a):
    cfg = CONFIG_PATH
    if cfg.exists():
        print(f"exists: {cfg}")
    else:
        data = load_json(FACTORY_DIR / "config.example.json")
        data["projects"] = []
        write_json(cfg, data)
        print(f"created {cfg}")
    (STATE_DIR / "jobs").mkdir(parents=True, exist_ok=True)


def cmd_project_add(a):
    path = CONFIG_PATH
    cfg = load_json(path)
    repo = str(Path(a.repo_path).resolve())
    cfg["projects"] = [p for p in cfg.get("projects", []) if p["name"] != a.name]
    cfg["projects"].append({"name": a.name, "repo_path": repo})
    write_json(path, cfg)
    print(f"registered project {a.name} -> {repo}")
    ddir = Path(repo) / ".factory"
    if a.scaffold:
        if ddir.exists():
            print(f"{ddir} already exists; not overwriting")
        else:
            shutil.copytree(FACTORY_ROOT / "domain-template" / ".factory", ddir)
            print(f"scaffolded domain harness at {ddir} — edit domain.md, config.json, checks.sh")
    elif not ddir.exists():
        print(f"note: no domain harness at {ddir}. Re-run with --scaffold or create it by hand.")


def cmd_ticket_add(a):
    proj = config.project(a.project)
    tcfg = config.domain_config(proj)["tracker"]
    if tcfg.get("type") != "local":
        raise FactoryError("`ticket add` only works with the local tracker; create tickets in your tracker")
    t = trackers.get(tcfg, a.project).add(a.title, a.body or "")
    print(f"{t['key']}  {t['title']}")


def cmd_pull(a):
    names = [a.project] if a.project else [p["name"] for p in config.factory_config().get("projects", [])]
    for n in names:
        for j in trackers.pull(n):
            print(f"enqueued {j['id']}  {j['ticket']['title']}")


def cmd_next(a):
    tasks = engine.dispatch(a.limit)
    if a.json:
        print(json.dumps(tasks, indent=2))
        return
    if not tasks:
        print("no agent tasks ready")
    for t in tasks:
        print(f"{t['job']}  {t['stage']}#{t['attempt']}  {t['agent']} ({t['model']})  brief={t['brief_path']}")


def cmd_complete(a):
    job = engine.complete(a.job)
    print(f"{job['id']} -> {job['stage']} ({job['status']})")


def cmd_save_result(a):
    """Persist an agent's final message when the agent could not write the file itself."""
    job = state.load(a.job)
    lock = job.get("lock") or {}
    text = sys.stdin.read()
    m = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    raw = m[-1] if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"status": "fail", "summary": "agent returned no parseable result JSON", "raw": text[-4000:]}
    path = state.result_path(a.job, lock.get("stage", "unknown"), lock.get("attempt", 0), a.agent)
    write_json(path, data)
    print(f"saved {path}")


def _dur(h):
    try:
        return (parse_time(h["finished_at"]) - parse_time(h["started_at"])).total_seconds()
    except Exception:
        return 0


def cmd_status(a):
    jobs = [state.load(a.job)] if a.job else state.all_jobs()
    if a.json:
        print(json.dumps(jobs, indent=2))
        return
    for j in jobs:
        secs = sum(_dur(h) for h in j["history"])
        cost = sum((h.get("data") or {}).get("usage", {}).get("cost_usd", 0) or 0 for h in j["history"])
        lock = f" [running {j['lock']['stage']}]" if j.get("lock") else ""
        print(f"{j['id']:<36} {j['status']:<15} {j['stage']:<12}{lock} risk={j.get('risk')} "
              f"time={secs/60:.1f}m cost=${cost:.2f}  {j['ticket']['title'][:50]}")
        if a.job:
            for h in j["history"]:
                print(f"   {h['stage']}#{h['attempt']:<2} {h['status']:<18} {_dur(h):>6.0f}s  {h['summary'][:140]}")
            for w in j.get("warnings", []):
                print(f"   warning: {w}")


def cmd_human(a):
    job = engine.human(a.job, a.decision, a.stage, a.note or "")
    print(f"{job['id']} -> {job['stage']} ({job['status']})")


def main(argv=None):
    p = argparse.ArgumentParser(prog="factory", description="Agentic software factory")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(fn=cmd_init)

    pa = sub.add_parser("project", help="manage projects").add_subparsers(dest="sub", required=True)
    s = pa.add_parser("add")
    s.add_argument("name"); s.add_argument("repo_path"); s.add_argument("--scaffold", action="store_true")
    s.set_defaults(fn=cmd_project_add)

    ta = sub.add_parser("ticket", help="local tracker tickets").add_subparsers(dest="sub", required=True)
    s = ta.add_parser("add")
    s.add_argument("project"); s.add_argument("title"); s.add_argument("--body")
    s.set_defaults(fn=cmd_ticket_add)

    s = sub.add_parser("pull", help="enqueue ready tickets from trackers")
    s.add_argument("project", nargs="?"); s.set_defaults(fn=cmd_pull)

    s = sub.add_parser("next", help="advance scripts, hand out agent tasks")
    s.add_argument("--json", action="store_true"); s.add_argument("--limit", type=int)
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("complete", help="aggregate agent results and transition")
    s.add_argument("job"); s.set_defaults(fn=cmd_complete)

    s = sub.add_parser("save-result", help="save agent final message (stdin) as its result")
    s.add_argument("job"); s.add_argument("agent"); s.set_defaults(fn=cmd_save_result)

    s = sub.add_parser("status")
    s.add_argument("job", nargs="?"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("human", help="human decision on a paused job")
    s.add_argument("job"); s.add_argument("decision", choices=["approve", "reject", "retry"])
    s.add_argument("--stage"); s.add_argument("--note")
    s.set_defaults(fn=cmd_human)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except FactoryError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
