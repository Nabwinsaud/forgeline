"""Shared helpers: paths, JSON IO, time, subprocess."""
from __future__ import annotations

import datetime as _dt
import json
import re
import os
import subprocess
from pathlib import Path
from typing import Any

# Where Forgeline itself is installed (plugin root or a git checkout).
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
AGENTS_DIR = PLUGIN_ROOT / "agents"
DEFAULTS_DIR = PLUGIN_ROOT / "defaults"
TEMPLATES_DIR = PLUGIN_ROOT / "templates"

DOMAIN_DIRNAME = ".factory"
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class FactoryError(Exception):
    pass


def user_config_path() -> Path:
    base = os.environ.get("FORGELINE_HOME") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "forgeline")
    return Path(base) / "config.json"


def find_repo_root(start: Path | None = None) -> Path:
    """The app repo is the nearest ancestor with a .factory/ dir (or FORGELINE_REPO)."""
    env = os.environ.get("FORGELINE_REPO")
    if env:
        return Path(env).resolve()
    cur = (start or Path.cwd()).resolve()
    for p in (cur, *cur.parents):
        if (p / DOMAIN_DIRNAME / "config.json").exists():
            # a job worktree lives inside .factory/worktrees/<job>; climb out of it
            if p.parent.name == "worktrees" and p.parent.parent.name == DOMAIN_DIRNAME:
                continue
            return p
    raise FactoryError("no .factory/ found here or above. Run `forgeline init` in your app repo first.")


def git_root(start: Path | None = None) -> Path | None:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or Path.cwd(),
                          capture_output=True, text=True)
    return Path(proc.stdout.strip()) if proc.returncode == 0 else None


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def parse_time(s: str) -> _dt.datetime:
    """ISO 8601 from us, GitHub (`...Z`) or Jira (`...000+0000`). Naive times are taken as UTC."""
    s = s.strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s)
    t = _dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FactoryError(f"missing file: {path}")
    with path.open() as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise FactoryError(f"invalid JSON in {path}: {e}") from e


def write_json(path: Path, data: Any) -> None:
    """Atomic write so an interrupted run never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if k.startswith("$"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def run(cmd: list[str], cwd: Path | str | None = None, check: bool = True,
        env: dict | None = None, timeout: int | None = None, input: str | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, input=input,
                          env={**os.environ, **(env or {})}, timeout=timeout)
    if check and proc.returncode != 0:
        raise FactoryError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc


def slugify(text: str, max_len: int = 40) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:max_len].strip("-") or "job"
