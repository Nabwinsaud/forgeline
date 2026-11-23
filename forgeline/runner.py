"""Headless runner: drive the factory without an interactive session.

    forgeline run                    # Claude Code headless (claude -p), default
    forgeline run --runner codex     # Codex CLI (codex exec)

Each agent task becomes one CLI process in the job's worktree. Different jobs run in
parallel (up to `concurrency`); agents inside one stage run in parallel only when the
stage says so. Real token usage and cost are captured from the runner's output.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import compose, config, engine, state, trackers
from .util import FactoryError, load_json, run as sh, write_json


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    meta = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def _extract_json(text: str) -> dict | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    for raw in reversed(blocks or [text]):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _claude(task: dict, prompt: str, role: str, tools: str, rcfg: dict) -> tuple[str, dict]:
    cmd = ["claude", "-p", "--model", task["model"], "--output-format", "json",
           "--permission-mode", rcfg.get("claude", {}).get("permission_mode", "acceptEdits"),
           "--add-dir", str(Path(task["result_path"]).parent.parent)]
    if role:
        cmd += ["--append-system-prompt", role]
    if tools:
        cmd += ["--allowedTools", *[t.strip() for t in tools.split(",") if t.strip()]]
    proc = sh(cmd, cwd=task["cwd"], check=False, input=prompt,
              timeout=int(rcfg.get("timeout_minutes", 45)) * 60)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout + proc.stderr, {}
    usage = out.get("usage") or {}
    return out.get("result", ""), {
        "input_tokens": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": out.get("total_cost_usd", 0) or 0,
    }


def _codex(task: dict, prompt: str, role: str, tools: str, rcfg: dict) -> tuple[str, dict]:
    last = Path(task["result_path"]).with_suffix(".codex.txt")
    c = rcfg.get("codex", {})
    cmd = ["codex", "exec", "-C", task["cwd"], "-s", c.get("sandbox", "workspace-write"),
           "--skip-git-repo-check", "-o", str(last)]
    if c.get("model"):
        cmd += ["-m", c["model"]]
    cmd.append((role + "\n\n" if role else "") + prompt)
    proc = sh(cmd, check=False, timeout=int(rcfg.get("timeout_minutes", 45)) * 60)
    text = last.read_text() if last.exists() else proc.stdout + proc.stderr
    return text, {}


RUNNERS = {"claude": _claude, "codex": _codex}


def run_task(task: dict, runner: str) -> None:
    rcfg = config.factory_config().get("runner", {})
    role_text, tools = "", ""
    if task.get("role_path"):
        rp = Path(task["role_path"])
        role_text = compose._strip_frontmatter(rp.read_text())
        tools = _frontmatter(rp).get("tools", "")
    prompt = Path(task["brief_path"]).read_text()
    final, usage = RUNNERS[runner](task, prompt, role_text, tools, rcfg)

    result_path = Path(task["result_path"])
    if result_path.exists():
        data = load_json(result_path)
    else:
        data = _extract_json(final) or {"status": "fail", "summary": "agent returned no result JSON",
                                         "raw": (final or "")[-4000:]}
    if usage and not (data.get("usage") or {}).get("cost_usd"):
        data["usage"] = usage
    write_json(result_path, data)


def _run_group(tasks: list[dict], runner: str, log) -> None:
    parallel = tasks[0].get("parallel") and len(tasks) > 1
    if parallel:
        with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
            list(ex.map(lambda t: _safe(t, runner, log), tasks))
    else:
        for t in tasks:
            _safe(t, runner, log)
    try:
        job = engine.complete(tasks[0]["job"])
        log(f"{job['id']}: {tasks[0]['stage']} -> {job['stage']} ({job['status']})")
    except FactoryError as e:
        log(f"{tasks[0]['job']}: {e}")


def _safe(task, runner, log):
    log(f"{task['job']}: {task['stage']}#{task['attempt']} {task['agent']} ({task['model']}) ...")
    try:
        run_task(task, runner)
    except Exception as e:  # a crashed agent is a failed result, never a crashed factory
        write_json(Path(task["result_path"]), {"status": "fail", "summary": f"runner error: {e}"})


def loop(runner: str | None = None, once: bool = False, max_ticks: int = 500, poll_seconds: int = 60,
         pull: bool = True, log=None) -> None:
    log = log or (lambda m: print(m, flush=True))
    runner = runner or config.factory_config().get("runner", {}).get("default", "claude")
    if runner not in RUNNERS:
        raise FactoryError(f"unknown runner {runner}; choose {sorted(RUNNERS)}")
    if pull:
        for j in trackers.pull():
            log(f"enqueued {j['id']}: {j['ticket']['title']}")
    workers = config.factory_config().get("concurrency", 3)
    for _ in range(max_ticks):
        tasks = engine.dispatch()
        if not tasks:
            waiting = [j for j in state.all_jobs() if j["status"] == "active" and not j.get("lock")]
            if waiting and not once:
                log(f"waiting on {[j['id'] + '@' + j['stage'] for j in waiting]}; next check in {poll_seconds}s")
                time.sleep(poll_seconds)
                continue
            log("nothing left to do")
            return
        groups: dict[tuple, list] = {}
        for t in tasks:
            groups.setdefault((t["job"], t["stage"]), []).append(t)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(lambda g: _run_group(g, runner, log), groups.values()))
        if once:
            return
