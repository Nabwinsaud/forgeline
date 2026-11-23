"""Small shared helpers: paths, JSON IO, time, subprocess."""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

FACTORY_ROOT = Path(os.environ.get("FACTORY_ROOT", Path(__file__).resolve().parent.parent))
FACTORY_DIR = FACTORY_ROOT / "factory"
STATE_DIR = Path(os.environ.get("FACTORY_STATE_DIR", FACTORY_DIR / "state"))
CONFIG_PATH = Path(os.environ.get("FACTORY_CONFIG", FACTORY_DIR / "config.json"))
BASE_AGENTS_DIR = FACTORY_ROOT / "base" / "agents"


class FactoryError(Exception):
    pass


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def parse_time(s: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(s)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FactoryError(f"missing file: {path}")
    with path.open() as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Atomic write so an interrupted orchestrator never leaves half a job file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def run(cmd: list[str], cwd: Path | str | None = None, check: bool = True,
        env: dict | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        env={**os.environ, **(env or {})}, timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise FactoryError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
        )
    return proc


def slugify(text: str, max_len: int = 40) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:max_len].strip("-") or "job"


RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
