"""Prompt composition: base agent role + app domain rules -> one brief per agent task.

brief = agent role                   (agents/<agent>.md, or the plugin subagent itself)
      + domain harness               (<repo>/.factory/domain.md)
      + domain notes for this agent  (<repo>/.factory/agents/<agent>.md)
      + job context                  (ticket, spec, prior feedback, paths, env)
      + output contract              (where and how to write the result JSON)

The brief is harness-neutral markdown, so Claude Code subagents, `claude -p`,
the Agent SDK, or `codex exec` can all consume the same file.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, state
from .util import AGENTS_DIR, FactoryError

FEEDBACK_STAGES = ["test", "security", "gate", "review", "approve"]


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip()
    return text


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def base_prompt(agent: dict) -> str:
    if "domain" in agent:  # domain-defined reviewer
        return ""
    path = AGENTS_DIR / f"{agent['name']}.md"
    if not path.exists():
        raise FactoryError(f"no base agent prompt: {path}")
    return _strip_frontmatter(path.read_text())


def _feedback(job: dict) -> str:
    """Failures from later stages, so a builder retry knows exactly what to fix."""
    chunks = []
    for st in FEEDBACK_STAGES:
        for r in state.latest_results(job, st):
            if r.get("status") in ("fail", "changes_requested"):
                body = r.get("summary", "")
                findings = r.get("data", {}).get("findings") if isinstance(r.get("data"), dict) else None
                if findings:
                    body += "\n" + json.dumps(findings, indent=2)[:6000]
                chunks.append(f"### {st} / {r.get('agent', '?')}\n{body}")
    for h in reversed(job["history"]):
        if h["stage"] == "gate" and h["status"] == "fail":
            chunks.append(f"### gate (deterministic checks)\n{h['summary'][-4000:]}")
            break
    last = job["history"][-1] if job["history"] else None
    if last and last["stage"] == "merge" and last["status"] == "changes_requested":
        chunks.insert(0, f"### merge (base branch moved on)\n{last['summary'][-4000:]}")
    return "\n\n".join(chunks)


def role_path(agent: dict) -> Path | None:
    if "domain" in agent:
        return None
    return AGENTS_DIR / f"{agent['name']}.md"


def brief(job: dict, sdef: dict, agent: dict, attempt: int, include_role: bool = False) -> Path:
    """Compose the task brief.

    Claude Code runs base roles as plugin subagents (forgeline:<role>), whose system prompt
    already *is* the role, so the brief carries only domain + job context. Headless runners
    (claude -p, codex exec) pass include_role=True to get one self-contained prompt.
    Domain reviewers have no plugin agent, so their role is always included.
    """
    proj = config.project(job["project"])
    ddir = config.domain_dir(proj)
    dcfg = config.domain_config(proj)
    name = agent["name"]

    parts = [f"# Factory task: {name} @ {sdef['id']} (attempt {attempt})"]

    if "domain" in agent:
        parts.append("## Your role (domain reviewer)\n" + _read(ddir / agent["domain"]["prompt"]))
    elif include_role:
        parts.append("## Your role\n" + base_prompt(agent))
    else:
        parts.append(f"You are running as the `{name}` role. Follow your role instructions; "
                     "the sections below are this job's domain rules and context.")

    domain_md = _read(ddir / "domain.md")
    if domain_md:
        parts.append("## Domain harness (business rules — these override generic advice)\n" + domain_md)
    agent_notes = _read(ddir / "agents" / f"{name}.md")
    if agent_notes:
        parts.append(f"## Domain notes for {name}\n" + agent_notes)

    t = job["ticket"]
    ctx = [
        f"- Job: `{job['id']}`  project: `{job['project']}`",
        f"- Ticket: {t['tracker']}:{t['key']} — {t['title']}" + (f" ({t['url']})" if t.get("url") else ""),
        f"- Risk: {job.get('risk')}  size: {job.get('size')}  areas: {job.get('areas')}",
        f"- Repo: `{proj['repo_path']}`",
    ]
    if job.get("worktree"):
        ctx.append(f"- Work ONLY inside worktree: `{job['worktree']}` (branch `{job['branch']}`)")
    if job.get("pr"):
        ctx.append(f"- PR: {job['pr'].get('url') or job['pr'].get('ref')}")
    if sdef.get("env"):
        env = dcfg["envs"].get(sdef["env"], {})
        ctx.append(f"- Environment: `{sdef['env']}` url: {env.get('url', 'local — see domain config')}")
    ctx.append(f"- Areas map: {json.dumps(dcfg['areas'])}")
    ctx.append(f"- Domain commands: {json.dumps(dcfg.get('commands', {}))}")
    parts.append("## Job context\n" + "\n".join(ctx))
    parts.append("## Ticket body\n" + (t.get("body") or "(empty)"))

    spec_path = state.job_dir(job["id"]) / "spec.md"
    if spec_path.exists() and sdef["id"] != "spec":
        parts.append("## Spec (acceptance criteria are the contract)\n" + spec_path.read_text())

    fb = _feedback(job)
    if fb and sdef["id"] in ("build", "test", "security", "review", "approve"):
        parts.append("## Feedback from previous attempts (fix these first)\n" + fb)

    if sdef["id"] == "approve":
        reviews = state.latest_results(job, "review")
        parts.append("## Review results\n" + json.dumps(reviews, indent=2)[:8000])
        gate = next((h for h in reversed(job["history"]) if h["stage"] == "gate"), None)
        parts.append("## Gate result\n" + json.dumps(gate, indent=2)[:3000])

    result_path = state.result_path(job["id"], sdef["id"], attempt, name)
    parts.append(f"""## Output contract (mandatory)
When finished, write exactly one JSON file to:
`{result_path}`
(If you cannot write files, print the JSON as your final message inside a ```json block
and the orchestrator will save it.)

```json
{{
  "status": "pass | fail | changes_requested | needs_human | reject | skip",
  "summary": "one paragraph, what you did / found",
  "data": {{ }},
  "usage": {{ "input_tokens": 0, "output_tokens": 0, "cost_usd": 0 }}
}}
```
Stage-specific `data` keys are described in your role section. Do not invent other statuses.
Never merge, push to the base branch, or change ticket status yourself — the factory does that.""")
    if sdef["id"] == "spec":
        parts.append("Put the full spec markdown in `data.spec_markdown`.")

    suffix = ".full" if include_role else ""
    out = state.briefs_dir(job["id"]) / f"{sdef['id']}.{attempt}.{name}{suffix}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(parts) + "\n")
    return out
