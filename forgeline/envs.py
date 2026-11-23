"""Environment adapters: has the merged commit reached dev / stg yet?

none     : no real env; pass immediately (QA runs against `local_url` if given).
url_poll : GET url + version_path; pass when the body contains the merge sha.
command  : run a shell command (any CI/CD). exit 0 = deployed, 75 = pending, else fail.
           FACTORY_MERGE_SHA and FACTORY_ENV are exported to it.
"""
from __future__ import annotations

import urllib.error
import urllib.request

from .util import run


def get(env_cfg: dict):
    return {"none": NoEnv, "url_poll": UrlPoll, "command": CommandEnv}[env_cfg.get("type", "none")]()


class NoEnv:
    def check(self, job, cfg):
        return "pass", "no deploy target configured; QA will run locally"


class UrlPoll:
    def check(self, job, cfg):
        sha = (job.get("merge_sha") or "")[:7]
        url = cfg["url"].rstrip("/") + cfg.get("version_path", "/version")
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                body = r.read(4096).decode(errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            return "pending", f"{url} unreachable: {exc}"
        if sha and sha in body:
            return "pass", f"{url} reports {sha}"
        return "pending", f"{url} does not report {sha} yet"


class CommandEnv:
    def check(self, job, cfg):
        proc = run(["bash", "-c", cfg["command"]], check=False, timeout=300,
                   env={"FACTORY_MERGE_SHA": job.get("merge_sha") or "", "FACTORY_ENV": cfg.get("name", "")})
        if proc.returncode == 0:
            return "pass", proc.stdout[-500:]
        if proc.returncode == 75:
            return "pending", proc.stdout[-500:]
        return "fail", (proc.stdout + proc.stderr)[-1500:]
