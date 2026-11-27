"""Jira Cloud via REST v3. Credentials come only from env vars, never config files.

.factory/config.json:
  "tracker": {
    "type": "jira",
    "base_url": "https://your-site.atlassian.net",
    "jql": "project = APP AND status = \"Ready for Dev\" AND labels = factory",
    "status_map": {"in_progress": "In Progress", "in_review": "In Review",
                   "blocked": "Blocked", "done": "Done"},
    "email_env": "JIRA_EMAIL", "token_env": "JIRA_API_TOKEN"
  }
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request


class JiraTracker:
    def __init__(self, cfg: dict, project_name: str):
        self.base = cfg["base_url"].rstrip("/")
        self.jql = cfg["jql"]
        self.map = cfg.get("status_map", {})
        email = os.environ[cfg.get("email_env", "JIRA_EMAIL")]
        token = os.environ[cfg.get("token_env", "JIRA_API_TOKEN")]
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def _req(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": self.auth, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    @staticmethod
    def _adf_text(node) -> str:
        if not node:
            return ""
        if isinstance(node, str):
            return node
        text = node.get("text", "")
        for c in node.get("content", []) or []:
            text += JiraTracker._adf_text(c)
        if node.get("type") in ("paragraph", "heading", "listItem"):
            text += "\n"
        return text

    def list_ready(self) -> list[dict]:
        data = self._req("POST", "/rest/api/3/search/jql",
                         {"jql": self.jql, "fields": ["summary", "description"], "maxResults": 50})
        return [{"tracker": "jira", "key": i["key"], "title": i["fields"]["summary"],
                 "body": self._adf_text(i["fields"].get("description")),
                 "url": f"{self.base}/browse/{i['key']}"} for i in data.get("issues", [])]

    def set_status(self, key: str, logical: str) -> None:
        target = self.map.get(logical)
        if not target:
            return
        transitions = self._req("GET", f"/rest/api/3/issue/{key}/transitions")["transitions"]
        match = next((t for t in transitions
                      if t["name"].lower() == target.lower() or t["to"]["name"].lower() == target.lower()), None)
        if match:
            self._req("POST", f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": match["id"]}})

    def comment(self, key: str, text: str) -> None:
        body = {"body": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line or " "}]}
            for line in text.splitlines()]}}
        self._req("POST", f"/rest/api/3/issue/{key}/comment", body)

    def comments(self, key: str) -> list[dict]:
        data = self._req("GET", f"/rest/api/3/issue/{key}/comment?orderBy=created&maxResults=100")
        return [{"at": c["created"], "text": self._adf_text(c.get("body")).strip(),
                 "author": (c.get("author") or {}).get("displayName")} for c in data.get("comments", [])]
