"""Linear via GraphQL. Credential from env var only.

.factory/config.json:
  "tracker": {
    "type": "linear",
    "team_key": "APP",
    "ready_state": "Todo",
    "label": "factory",
    "status_map": {"in_progress": "In Progress", "in_review": "In Review",
                   "blocked": "Blocked", "done": "Done"},
    "token_env": "LINEAR_API_KEY"
  }
"""
from __future__ import annotations

import json
import os
import urllib.request

API = "https://api.linear.app/graphql"


class LinearTracker:
    def __init__(self, cfg: dict, project_name: str):
        self.cfg = cfg
        self.map = cfg.get("status_map", {})
        self.token = os.environ[cfg.get("token_env", "LINEAR_API_KEY")]
        self._states = None

    def _gql(self, query: str, variables: dict) -> dict:
        req = urllib.request.Request(API, method="POST",
                                     data=json.dumps({"query": query, "variables": variables}).encode(),
                                     headers={"Authorization": self.token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if data.get("errors"):
            raise RuntimeError(data["errors"])
        return data["data"]

    def list_ready(self) -> list[dict]:
        flt = {"team": {"key": {"eq": self.cfg["team_key"]}},
               "state": {"name": {"eq": self.cfg.get("ready_state", "Todo")}}}
        if self.cfg.get("label"):
            flt["labels"] = {"name": {"eq": self.cfg["label"]}}
        q = "query($f: IssueFilter){ issues(filter:$f, first:50){ nodes{ identifier title description url } } }"
        nodes = self._gql(q, {"f": flt})["issues"]["nodes"]
        return [{"tracker": "linear", "key": n["identifier"], "title": n["title"],
                 "body": n.get("description") or "", "url": n["url"]} for n in nodes]

    def _state_id(self, name: str) -> str | None:
        if self._states is None:
            q = "query($k: String!){ teams(filter:{key:{eq:$k}}){ nodes{ states{ nodes{ id name } } } } }"
            teams = self._gql(q, {"k": self.cfg["team_key"]})["teams"]["nodes"]
            self._states = {s["name"].lower(): s["id"] for t in teams for s in t["states"]["nodes"]}
        return self._states.get(name.lower())

    def set_status(self, key: str, logical: str) -> None:
        target = self.map.get(logical)
        sid = target and self._state_id(target)
        if sid:
            q = "mutation($id: String!, $s: String!){ issueUpdate(id:$id, input:{stateId:$s}){ success } }"
            self._gql(q, {"id": key, "s": sid})

    def comment(self, key: str, text: str) -> None:
        q = "mutation($id: String!, $b: String!){ commentCreate(input:{issueId:$id, body:$b}){ success } }"
        self._gql(q, {"id": key, "b": text})
