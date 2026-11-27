"""forgeline — the CLI every orchestrator (Claude Code, Codex, CI, a human) uses."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import __version__, config, doctor, engine, init, runner, state, trackers
from .util import FactoryError, parse_time, write_json


def cmd_init(a):
    res = init.run(force=a.force, rules=a.rules, tracker=a.tracker, base_branch=a.base)
    print(json.dumps(res, indent=2) if a.json else init.summary(res))


def cmd_doctor(a):
    sys.exit(doctor.report())


def cmd_ticket_add(a):
    tcfg = config.domain_config()["tracker"]
    if tcfg.get("type") != "local":
        raise FactoryError("`ticket add` is for the local tracker. Create the ticket in your tracker "
                           "with the ready label/state, then run `forgeline pull`.")
    t = trackers.get(tcfg, config.project()["name"]).add(a.title, a.body or "")
    print(f"{t['key']}  {t['title']}")


def cmd_ticket_list(a):
    for t in trackers.get(config.domain_config()["tracker"], config.project()["name"]).list_ready():
        print(f"{t['key']:<12} {t['title']}")


def cmd_do(a):
    title = " ".join(a.request).strip()
    if not title:
        raise FactoryError('say what you want built, e.g. forgeline do "add a dark mode toggle"')
    job = trackers.do(title, a.body or "")
    print(f"started {job['id']}  {job['ticket']['title']}")
    if a.queue:
        print("queued. Run `forgeline run` (headless) or /forgeline:run in Claude Code to work on it.")
        return
    runner.loop(runner=a.runner, pull=False)


def cmd_pull(a):
    jobs = trackers.pull()
    for j in jobs:
        print(f"enqueued {j['id']}  {j['ticket']['title']}")
    if not jobs:
        print("no new ready tickets")


def cmd_next(a):
    tasks = engine.dispatch(a.limit)
    if a.json:
        print(json.dumps(tasks, indent=2))
        return
    if not tasks:
        print("no agent tasks ready")
    for t in tasks:
        print(f"{t['job']}  {t['stage']}#{t['attempt']}  {t['subagent_type']} ({t['model']})  brief={t['brief_path']}")


def cmd_complete(a):
    job = engine.complete(a.job)
    print(f"{job['id']} -> {job['stage']} ({job['status']})")


def cmd_save_result(a):
    """Persist an agent's final message (stdin) when the agent could not write the file itself."""
    job = state.load(a.job)
    lock = job.get("lock") or {}
    if not lock:
        raise FactoryError(f"{a.job} has no stage in flight")
    text = sys.stdin.read()
    data = runner._extract_json(text) or {"status": "fail", "summary": "agent returned no result JSON",
                                          "raw": text[-4000:]}
    path = state.result_path(a.job, lock["stage"], lock["attempt"], a.agent)
    write_json(path, data)
    print(f"saved {path}")


def cmd_run(a):
    runner.loop(runner=a.runner, once=a.once, max_ticks=a.max_ticks, poll_seconds=a.poll, pull=not a.no_pull)


def _dur(h):
    try:
        return (parse_time(h["finished_at"]) - parse_time(h["started_at"])).total_seconds()
    except Exception:
        return 0


def _cost(h):
    return ((h.get("data") or {}).get("usage") or {}).get("cost_usd", 0) or 0


def cmd_status(a):
    jobs = [state.load(a.job)] if a.job else state.all_jobs()
    if a.json:
        print(json.dumps(jobs, indent=2))
        return
    if not jobs:
        print("no jobs yet. Add a ticket and run `forgeline pull`.")
    for j in jobs:
        secs = sum(_dur(h) for h in j["history"])
        cost = sum(_cost(h) for h in j["history"])
        lock = f" [running {j['lock']['stage']}]" if j.get("lock") else ""
        print(f"{j['id']:<28} {j['status']:<15} {j['stage']:<12}{lock} risk={j.get('risk')} "
              f"time={secs/60:.1f}m cost=${cost:.2f}  {j['ticket']['title'][:50]}")
        if a.job:
            if j.get("status_reason"):
                print(f"   reason: {j['status_reason'][:300]}")
            for h in j["history"]:
                print(f"   {h['stage']:<11}#{h['attempt']:<2} {h['status']:<18} {_dur(h):>6.0f}s "
                      f"${_cost(h):.2f}  {h['summary'][:120]}")
            for w in j.get("warnings", []):
                print(f"   warning: {w}")


def cmd_report(a):
    """Factory metrics: pass rate, attempts, time and cost per stage. Use it to tune models and prompts."""
    stats = defaultdict(lambda: {"runs": 0, "pass": 0, "secs": 0.0, "cost": 0.0})
    jobs = state.all_jobs()
    for j in jobs:
        for h in j["history"]:
            s = stats[h["stage"]]
            s["runs"] += 1
            s["pass"] += h["status"] in ("pass", "skip")
            s["secs"] += _dur(h)
            s["cost"] += _cost(h)
    by_status = defaultdict(int)
    for j in jobs:
        by_status[j["status"]] += 1
    if a.json:
        print(json.dumps({"jobs": dict(by_status), "stages": stats}, indent=2))
        return
    print("jobs: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())) or "none")
    print(f"\n{'stage':<12} {'runs':>5} {'pass%':>6} {'avg time':>9} {'cost':>8}")
    for stage, s in stats.items():
        print(f"{stage:<12} {s['runs']:>5} {100*s['pass']/max(s['runs'],1):>5.0f}% "
              f"{s['secs']/max(s['runs'],1)/60:>8.1f}m ${s['cost']:>7.2f}")
    total = sum(s["cost"] for s in stats.values())
    done = by_status.get("complete", 0)
    print(f"\ntotal cost ${total:.2f}" + (f" · ${total/done:.2f} per shipped ticket" if done else ""))


def cmd_human(a):
    job = engine.human(a.job, a.decision, a.stage, a.note or "")
    print(f"{job['id']} -> {job['stage']} ({job['status']})")


def cmd_version(a):
    print(f"forgeline {__version__}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="forgeline", description="Agentic software factory harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="scaffold .factory/ in this repo")
    s.add_argument("--force", action="store_true")
    s.add_argument("--rules", default="auto", help="auto | none | comma list (go,typescript,python)")
    s.add_argument("--tracker", default="local", choices=["local", "github", "jira", "linear"])
    s.add_argument("--base", help="base branch (default: current branch)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_init)

    sub.add_parser("doctor", help="check tools, config and credentials").set_defaults(fn=cmd_doctor)

    t = sub.add_parser("ticket", help="local tracker").add_subparsers(dest="sub", required=True)
    s = t.add_parser("add"); s.add_argument("title"); s.add_argument("--body"); s.set_defaults(fn=cmd_ticket_add)
    t.add_parser("list").set_defaults(fn=cmd_ticket_list)

    s = sub.add_parser("do", help='start a job from one sentence: forgeline do "add dark mode"')
    s.add_argument("request", nargs="+", help="what you want built or fixed")
    s.add_argument("--body", help="more detail: acceptance criteria, out of scope, links")
    s.add_argument("--queue", action="store_true", help="only enqueue; don't start the headless runner")
    s.add_argument("--runner", choices=sorted(runner.RUNNERS))
    s.set_defaults(fn=cmd_do)

    sub.add_parser("pull", help="enqueue ready tickets").set_defaults(fn=cmd_pull)

    s = sub.add_parser("next", help="advance scripts, hand out agent tasks")
    s.add_argument("--json", action="store_true"); s.add_argument("--limit", type=int)
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("complete", help="aggregate agent results and transition")
    s.add_argument("job"); s.set_defaults(fn=cmd_complete)

    s = sub.add_parser("save-result", help="save an agent's final message (stdin) as its result")
    s.add_argument("job"); s.add_argument("agent"); s.set_defaults(fn=cmd_save_result)

    s = sub.add_parser("run", help="headless loop (claude -p / codex exec)")
    s.add_argument("--runner", choices=sorted(runner.RUNNERS))
    s.add_argument("--once", action="store_true")
    s.add_argument("--max-ticks", type=int, default=500)
    s.add_argument("--poll", type=int, default=60)
    s.add_argument("--no-pull", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("status"); s.add_argument("job", nargs="?"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("report", help="pass rate, time and cost per stage")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_report)

    s = sub.add_parser("human", help="decide on a paused job")
    s.add_argument("job"); s.add_argument("decision", choices=["approve", "reject", "retry"])
    s.add_argument("--stage"); s.add_argument("--note")
    s.set_defaults(fn=cmd_human)

    sub.add_parser("version").set_defaults(fn=cmd_version)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except FactoryError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
