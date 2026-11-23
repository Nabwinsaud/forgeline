"""Adapters: trackers (tickets), vcs (branches/PRs/merge), envs (deploy detection).

Interfaces
----------
Tracker(cfg, project_name)
    list_ready() -> list[ticket]          ticket = {tracker, key, title, body, url}
    set_status(key, logical)              logical in ready|in_progress|in_review|blocked|done
    comment(key, text)

Vcs(cfg, project)
    open_pr(job) -> {"number", "url", "ref"}   idempotent: push + create-or-reuse
    merge(job) -> merge_sha
    comment(job, text)

Env(cfg)
    check(job, env_cfg) -> (status, summary)    status in pass|pending|fail
"""
