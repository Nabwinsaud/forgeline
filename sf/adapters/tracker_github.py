"""GitHub Issues via the `gh` CLI. Status = labels; done = close.

.factory/config.json:
  "tracker": {
    "type": "github",
    "repo": "owner/name",
    "ready_label": "factory:ready",
    "status_map": {"in_progress": "factory:in-progress", "in_review": "factory:in-review",
                   "blocked": "factory:blocked", "done": "factory:done"}
  }
"""
from __future__ import annotations

import json

from ..util import run

DEFAULT_MAP = {
    "ready": "factory:ready", "in_progress": "factory:in-progress", "in_review": "factory:in-review",
    "blocked": "factory:blocked", "done": "factory:done",
}


class GitHubTracker:
    def __init__(self, cfg: dict, project_name: str):
        self.repo = cfg["repo"]
        self.ready = cfg.get("ready_label", DEFAULT_MAP["ready"])
        self.map = {**DEFAULT_MAP, **cfg.get("status_map", {})}

    def list_ready(self) -> list[dict]:
        out = run(["gh", "issue", "list", "--repo", self.repo, "--label", self.ready, "--state", "open",
                   "--limit", "50", "--json", "number,title,body,url"]).stdout
        return [{"tracker": "github", "key": str(i["number"]), "title": i["title"],
                 "body": i.get("body", ""), "url": i["url"]} for i in json.loads(out)]

    def set_status(self, key: str, logical: str) -> None:
        remove = [v for k, v in self.map.items() if k != logical]
        cmd = ["gh", "issue", "edit", key, "--repo", self.repo, "--add-label", self.map[logical]]
        for label in remove:
            cmd += ["--remove-label", label]
        run(cmd, check=False)  # removing absent labels is not an error worth failing on
        if logical == "done":
            run(["gh", "issue", "close", key, "--repo", self.repo, "--reason", "completed"])

    def comment(self, key: str, text: str) -> None:
        run(["gh", "issue", "comment", key, "--repo", self.repo, "--body", text])
