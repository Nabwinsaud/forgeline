"""`forgeline watch` (live view of every job) and `forgeline replay` (what happened, step by step)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time

from . import config, state
from .util import load_json, parse_time

TERMINAL = ("complete", "rejected")
STATUS_COLOR = {"active": "36", "awaiting_human": "33", "blocked": "31", "complete": "32", "rejected": "90"}
VERDICT_ICON = {"pass": "✓", "skip": "✓", "fail": "✗", "changes_requested": "↺", "needs_human": "?",
                "reject": "⊘", "pending": "…"}


def _color(on: bool):
    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if on else text
    return c


def _secs(h: dict) -> float:
    try:
        return (parse_time(h["finished_at"]) - parse_time(h["started_at"])).total_seconds()
    except Exception:
        return 0.0


def _cost(h: dict) -> float:
    return ((h.get("data") or {}).get("usage") or {}).get("cost_usd", 0) or 0


def _ago(iso: str | None) -> str:
    if not iso:
        return ""
    secs = (_dt.datetime.now(_dt.timezone.utc) - parse_time(iso)).total_seconds()
    if secs < 90:
        return f"{secs:.0f}s"
    if secs < 5400:
        return f"{secs / 60:.0f}m"
    return f"{secs / 3600:.1f}h"


def _rail(job: dict, c) -> str:
    """intake ✓ spec ✓ build ● test · ...: where the job is in the pipeline."""
    try:
        stages = [s["id"] for s in config.pipeline()["stages"]]
    except Exception:
        return ""
    last = {h["stage"]: h["status"] for h in job["history"]}
    here = (job.get("lock") or {}).get("stage") or job.get("paused_stage") or job["stage"]
    out = []
    for sid in stages:
        if sid == here and job["status"] not in TERMINAL:
            mark = {"awaiting_human": c("33", "‖"), "blocked": c("31", "✗")}.get(job["status"], c("36", "●"))
        elif sid in last:
            st = last[sid]
            mark = c("32", "✓") if st in ("pass", "skip") else c("31", VERDICT_ICON.get(st, "·"))
        else:
            mark = c("90", "·")
        out.append(f"{sid} {mark}")
    return "  ".join(out)


def frame(color: bool = False, show_done: int = 5) -> str:
    c = _color(color)
    jobs = state.all_jobs()
    live = [j for j in jobs if j["status"] not in TERMINAL]
    done = sorted((j for j in jobs if j["status"] in TERMINAL), key=lambda j: j.get("updated_at", ""),
                  reverse=True)[:show_done]
    total = sum(_cost(h) for j in jobs for h in j["history"])
    now = _dt.datetime.now().strftime("%H:%M:%S")
    lines = [c("1", "forgeline watch") + c("90", f"   {now}   {len(live)} in flight · "
                                                f"{sum(j['status'] == 'complete' for j in jobs)} shipped · "
                                                f"${total:.2f} total   (Ctrl+C to quit)"), ""]
    if not jobs:
        lines.append('no jobs yet. Try: forgeline do "add a health endpoint"')
    for j in live + done:
        secs = sum(_secs(h) for h in j["history"])
        cost = sum(_cost(h) for h in j["history"])
        status = c(STATUS_COLOR.get(j["status"], "0"), f"{j['status']:<14}")
        lines.append(f"{c('1', j['id']):<30} {status} {j['ticket']['title'][:56]}")
        lines.append(f"   risk={j.get('risk') or '?'}  time={secs / 60:.1f}m  cost=${cost:.2f}"
                     + (f"  PR {j['pr'].get('url') or j['pr'].get('ref')}" if j.get("pr") else ""))
        if j["status"] not in TERMINAL:
            lines.append("   " + _rail(j, c))
        lock = j.get("lock")
        if lock:
            agents = ", ".join(a["name"] for a in lock.get("agents", []))
            lines.append(c("36", f"   running {lock['stage']}#{lock['attempt']} ({agents}) for {_ago(lock.get('started_at'))}"))
            limit = config.factory_config().get("runner", {}).get("timeout_minutes", 45)
            try:
                age = (_dt.datetime.now(_dt.timezone.utc) - parse_time(lock["started_at"])).total_seconds() / 60
            except Exception:
                age = 0
            if age > limit * 2:
                lines.append(c("33", "   looks stale: the session running it probably stopped. "
                                     "`forgeline run` or /forgeline:run picks it up again"))
        q = j.get("questions") or {}
        if q.get("open"):
            for i, item in enumerate(q["items"], 1):
                lines.append(c("33", f"   ? {i}. {item}"))
            lines.append(c("90", f"   reply on the ticket, or: forgeline answer {j['id']} \"...\""))
        elif j["status"] in ("awaiting_human", "blocked") and j.get("status_reason"):
            lines.append(c("33", f"   {j['status_reason'][:160]}"))
        if j["history"] and not lock:
            h = j["history"][-1]
            icon = VERDICT_ICON.get(h["status"], "·")
            lines.append(c("90", f"   last: {h['stage']}#{h['attempt']} {icon} {h['summary'][:110]}"))
        lines.append("")
    return "\n".join(lines)


def watch(interval: float = 2.0, once: bool = False) -> None:
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    if once:
        print(frame(color))
        return
    try:
        while True:
            out = frame(color)
            sys.stdout.write("\033[H\033[2J" + out + "\n")
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        print()


def replay(job_id: str) -> str:
    """The job's story in order: every stage, every agent's verdict, questions, rebases, merge."""
    job = state.load(job_id)
    t = job["ticket"]
    lines = [f"# {job['id']}: {t['title']}", "",
             f"ticket {t['tracker']}:{t['key']}" + (f"  {t['url']}" if t.get("url") else ""),
             f"status {job['status']}  risk {job.get('risk')}  size {job.get('size')}  areas {job.get('areas')}"]
    if job.get("pr"):
        lines.append(f"PR {job['pr'].get('url') or job['pr'].get('ref')}")
    if job.get("merge_sha"):
        lines.append(f"merged {job['merge_sha'][:10]}")
    start = job["history"][0]["started_at"] if job["history"] else job.get("created_at")
    lines.append("")
    rebases = list(job.get("rebases") or [])
    for h in job["history"]:
        try:
            at = f"+{(parse_time(h['started_at']) - parse_time(start)).total_seconds() / 60:5.1f}m"
        except Exception:
            at = "       "
        icon = VERDICT_ICON.get(h["status"], "·")
        step = f"{h['stage']}#{h['attempt']}"
        lines.append(f"{at}  {step:<14} {icon} {h['status']:<17} "
                     f"{_secs(h):>5.0f}s  ${_cost(h):.2f}")
        per_agent = sorted(state.results_dir(job["id"]).glob(f"{h['stage']}.{h['attempt']}.*.json")) \
            if h["attempt"] else []
        if per_agent:
            for p in per_agent:
                r = load_json(p, {}) or {}
                agent = p.stem.split(".", 2)[2]
                data = r.get("data") if isinstance(r.get("data"), dict) else {}
                findings = data.get("findings") or []
                extra = f" ({len(findings)} findings)" if findings else ""
                lines.append(f"          {agent}: {VERDICT_ICON.get(r.get('status'), '·')} "
                             f"{(r.get('summary') or '').strip()[:300]}{extra}")
                for f in findings[:5]:
                    text = f.get("issue") or f.get("summary") or json.dumps(f)[:160] if isinstance(f, dict) else str(f)
                    lines.append(f"            - {str(text)[:160]}")
                if data.get("questions"):
                    for q in data["questions"]:
                        lines.append(f"            ? {q}")
        else:
            lines.append(f"          {h['summary'][:600]}".replace("\n", "\n          "))
        if h["stage"] == "merge" and rebases and h["status"] == "pass":
            rb = rebases.pop(0)
            lines.append(f"          rebased {rb['from']} → {rb['to']} onto {rb['onto']}, gate re-run")
    for a in job.get("answers") or []:
        lines += ["", f"answers from {a.get('by', 'human')}: {a['answer'][:500]}"]
    if job.get("warnings"):
        lines += ["", "warnings:"] + [f"  - {w}" for w in job["warnings"]]
    total_secs = sum(_secs(h) for h in job["history"])
    total_cost = sum(_cost(h) for h in job["history"])
    lines += ["", f"total {total_secs / 60:.1f}m of agent and script time, ${total_cost:.2f}"]
    return "\n".join(lines)
