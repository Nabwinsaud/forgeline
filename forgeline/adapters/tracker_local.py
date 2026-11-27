"""File-based tracker. Default. Lets you run the whole factory with zero external accounts.

Tickets: <repo>/.factory/tickets/<key>.json (commit them or not, your choice)
Add one: forgeline ticket add "title" --body "..."
"""
from __future__ import annotations

from .. import config
from ..util import load_json, now, write_json


class LocalTracker:
    def __init__(self, cfg: dict, project_name: str):
        self.cfg = cfg
        self.dir = config.domain_dir() / "tickets"

    def _path(self, key):
        return self.dir / f"{key}.json"

    def add(self, title: str, body: str = "", status: str = "ready") -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        key = f"T-{len(list(self.dir.glob('*.json'))) + 1:04d}"
        t = {"key": key, "title": title, "body": body, "status": status, "comments": [], "created_at": now()}
        write_json(self._path(key), t)
        return t

    def list_ready(self) -> list[dict]:
        if not self.dir.exists():
            return []
        out = []
        for p in sorted(self.dir.glob("*.json")):
            t = load_json(p)
            if t["status"] == "ready":
                out.append({"tracker": "local", "key": t["key"], "title": t["title"],
                            "body": t.get("body", ""), "url": str(p)})
        return out

    def set_status(self, key: str, logical: str) -> None:
        t = load_json(self._path(key))
        t["status"] = logical
        write_json(self._path(key), t)

    def comment(self, key: str, text: str) -> None:
        t = load_json(self._path(key))
        t.setdefault("comments", []).append({"at": now(), "text": text})
        write_json(self._path(key), t)

    def comments(self, key: str) -> list[dict]:
        t = load_json(self._path(key))
        return [{"at": c["at"], "text": c.get("text", ""), "author": c.get("by")} for c in t.get("comments", [])]
