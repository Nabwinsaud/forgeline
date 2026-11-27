"""`forgeline learn`: turn what past jobs went through into proposals.

- Recurring findings: the same kind of problem flagged by reviewers/testers in several jobs is a
  rule that belongs in domain.md (or a check in checks.sh), so the builder gets it right first time.
- Flaky gate: the gate failed and then passed on the very same commit.
- Cost by size: what a trivial / small / standard ticket really costs here.

Deterministic and local: no model calls. `/forgeline:learn` hands the JSON to an agent to phrase
the rules and edit domain.md with the user's OK. `--apply` appends the proposals directly.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import config, state
from .util import load_json

FINDING_STAGES = ("test", "security", "review", "approve", "qa_dev", "qa_stg")
SECTION = "## Lessons from past reviews"
STOP = set("""a an the and or but if then else of to in on at for from by with without into onto is are was
were be been being this that these those it its as not no do does did should must can could would will
you your we our they their there here than so such very also just only all any each every same other
more most less least use used using add added adds make makes made code file files function line""".split())


def _text(f) -> str:
    if isinstance(f, dict):
        return str(f.get("issue") or f.get("summary") or f.get("description") or f.get("message") or "")
    return str(f)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_]+", text.lower())
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words if w not in STOP and len(w) > 2}


def _similar(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def collect_findings() -> list[dict]:
    out = []
    for job in state.all_jobs():
        rdir = state.results_dir(job["id"])
        if not rdir.exists():
            continue
        for p in sorted(rdir.glob("*.json")):
            stage, _attempt, agent = p.stem.split(".", 2)
            if stage not in FINDING_STAGES:
                continue
            r = load_json(p, {}) or {}
            data = r.get("data") if isinstance(r.get("data"), dict) else {}
            for f in data.get("findings") or []:
                text = _text(f).strip()
                sev = (f.get("severity") if isinstance(f, dict) else None) or ""
                if not text or sev in ("nit", "low", "info"):
                    continue
                out.append({"job": job["id"], "stage": stage, "agent": agent, "text": text,
                            "severity": sev, "file": f.get("file", "") if isinstance(f, dict) else "",
                            "fix": f.get("fix", "") if isinstance(f, dict) else "", "tokens": _tokens(text)})
    return out


def cluster(findings: list[dict], threshold: float = 0.6) -> list[list[dict]]:
    """Greedy single-pass clustering on word overlap. Small data, readable results."""
    groups: list[dict] = []
    for f in findings:
        best, score = None, 0.0
        for g in groups:
            s = _similar(f["tokens"], g["tokens"])
            if s > score:
                best, score = g, s
        if best is not None and score >= threshold:
            best["items"].append(f)
            best["tokens"] |= f["tokens"]
        else:
            groups.append({"tokens": set(f["tokens"]), "items": [f]})
    return [g["items"] for g in groups]


def recurring(min_jobs: int = 2) -> list[dict]:
    out = []
    for items in cluster(collect_findings()):
        jobs = sorted({i["job"] for i in items})
        if len(jobs) < min_jobs:
            continue
        rep = min(items, key=lambda i: len(i["text"]))  # the shortest phrasing reads best as a rule
        fixes = [i["fix"] for i in items if i.get("fix")]
        out.append({"rule": rep["text"].rstrip("."), "fix": min(fixes, key=len) if fixes else "",
                    "count": len(items), "jobs": jobs, "agents": sorted({i["agent"] for i in items}),
                    "examples": [i["text"] for i in items[:3]]})
    return sorted(out, key=lambda r: (-len(r["jobs"]), -r["count"]))


def flaky_gate() -> list[dict]:
    out = []
    for job in state.all_jobs():
        gates = [h for h in job["history"] if h["stage"] == "gate"]
        for prev, nxt in zip(gates, gates[1:]):
            sha_a = (prev.get("data") or {}).get("sha")
            sha_b = (nxt.get("data") or {}).get("sha")
            if prev["status"] == "fail" and nxt["status"] == "pass" and sha_a and sha_a == sha_b:
                out.append({"job": job["id"], "sha": sha_a[:10], "failure": prev["summary"][-300:]})
    return out


def cost_by_size() -> dict:
    acc: dict[str, list[float]] = defaultdict(list)
    for job in state.all_jobs():
        if job["status"] != "complete":
            continue
        cost = sum(((h.get("data") or {}).get("usage") or {}).get("cost_usd", 0) or 0 for h in job["history"])
        acc[job.get("size") or "unknown"].append(cost)
    return {k: {"jobs": len(v), "avg_usd": round(sum(v) / len(v), 2)} for k, v in acc.items()}


def analyse(min_jobs: int = 2) -> dict:
    return {"recurring_findings": recurring(min_jobs), "flaky_gate": flaky_gate(), "cost_by_size": cost_by_size()}


def render(res: dict) -> str:
    lines = []
    rec = res["recurring_findings"]
    if rec:
        lines.append("Recurring findings (add these to .factory/domain.md so builders get them right first time):")
        for i, r in enumerate(rec, 1):
            lines.append(f"  {i}. {r['rule']}")
            if r["fix"]:
                lines.append(f"     fix: {r['fix'][:200]}")
            lines.append(f"     seen {r['count']}x in {len(r['jobs'])} jobs ({', '.join(r['jobs'][:4])}) by {', '.join(r['agents'])}")
    else:
        lines.append("No recurring findings yet. They show up once the same problem is flagged in 2+ jobs.")
    if res["flaky_gate"]:
        lines += ["", "Flaky gate (failed, then passed on the same commit). Fix or quarantine these checks:"]
        lines += [f"  - {f['job']} @ {f['sha']}: {f['failure'].strip().splitlines()[-1][:160]}" for f in res["flaky_gate"]]
    if res["cost_by_size"]:
        lines += ["", "What tickets cost here (shipped jobs):"]
        lines += [f"  {k:<9} ${v['avg_usd']:.2f} avg over {v['jobs']} job(s)" for k, v in sorted(res["cost_by_size"].items())]
    if rec:
        lines += ["", "Next: `forgeline learn --apply` appends these to domain.md (review the diff), or run "
                      "/forgeline:learn to have an agent phrase them first."]
    return "\n".join(lines)


def apply(res: dict) -> int:
    """Append recurring findings to domain.md under a lessons section. Skips ones already there."""
    path = config.domain_dir() / "domain.md"
    text = path.read_text() if path.exists() else ""
    known = text.lower()
    new = []
    for r in res["recurring_findings"]:
        if r["rule"].lower() in known:
            continue
        line = f"- {r['rule']}." + (f" Fix: {r['fix'].rstrip('.')}." if r["fix"] else "") + \
               f" (flagged in {len(r['jobs'])} jobs)"
        new.append(line)
    if not new:
        return 0
    if SECTION not in text:
        text = text.rstrip() + f"\n\n{SECTION}\n\nLearned by `forgeline learn` from repeated review findings. " \
                               "Edit or delete freely.\n"
    path.write_text(text.rstrip() + "\n" + "\n".join(new) + "\n")
    return len(new)
