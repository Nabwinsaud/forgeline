"""Layered configuration.

defaults/config.json          shipped with Forgeline (models, policy, concurrency)
~/.config/forgeline/config.json   your personal overrides (optional)
<repo>/.factory/config.json   this app's domain harness (tracker, vcs, envs, areas, policy, models)

Later layers win. Policy can be tightened per repo.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from .util import (DEFAULTS_DIR, DOMAIN_DIRNAME, FactoryError, deep_merge, find_repo_root, load_json,
                   user_config_path)

DOMAIN_DEFAULTS = {
    "tracker": {"type": "local"},
    "vcs": {"type": "local", "base_branch": "main"},
    "envs": {"dev": {"type": "none"}, "stg": {"type": "none"}},
    "areas": {"backend": ["backend/"], "frontend": ["frontend/"]},
    "commands": {},
    "domain_reviewers": [],
    "policy": {},
    "models": {},
}


@functools.lru_cache(maxsize=None)
def _load(repo: str) -> dict:
    base = load_json(DEFAULTS_DIR / "config.json")
    user = load_json(user_config_path(), default={})
    domain = load_json(Path(repo) / DOMAIN_DIRNAME / "config.json")
    merged = deep_merge(deep_merge(base, user), {k: domain[k] for k in ("models", "policy", "concurrency",
                                                                          "default_max_attempts",
                                                                          "lock_timeout_minutes",
                                                                          "runner") if k in domain})
    dom = deep_merge(DOMAIN_DEFAULTS, domain)
    return {"factory": merged, "domain": dom}


def reload() -> None:
    _load.cache_clear()


def repo_root() -> Path:
    return find_repo_root()


def factory_config() -> dict:
    return _load(str(repo_root()))["factory"]


def domain_config(proj: dict | None = None) -> dict:
    root = Path(proj["repo_path"]) if proj else repo_root()
    return _load(str(root))["domain"]


def project(name: str | None = None) -> dict:
    root = repo_root()
    return {"name": root.name, "repo_path": str(root)}


def domain_dir(proj: dict | None = None) -> Path:
    return Path((proj or project())["repo_path"]) / DOMAIN_DIRNAME


def state_dir() -> Path:
    return domain_dir() / "state"


def pipeline() -> dict:
    custom = domain_dir() / "pipeline.json"
    return load_json(custom if custom.exists() else DEFAULTS_DIR / "pipeline.json")


def model_for(agent: str) -> str:
    models = factory_config().get("models", {})
    return models.get(agent, models.get("default", "sonnet"))


def validate() -> list[str]:
    """Return a list of human-readable problems with the current configuration."""
    problems = []
    try:
        dom = domain_config()
    except FactoryError as e:
        return [str(e)]
    if dom["tracker"].get("type") not in ("local", "github", "jira", "linear"):
        problems.append(f"tracker.type unknown: {dom['tracker'].get('type')}")
    if dom["vcs"].get("type") not in ("local", "github"):
        problems.append(f"vcs.type unknown: {dom['vcs'].get('type')}")
    if dom["vcs"].get("type") == "github" and not dom["vcs"].get("repo"):
        problems.append("vcs.repo required for github (owner/name)")
    for name, env in dom["envs"].items():
        if isinstance(env, dict) and env.get("type") not in ("none", "url_poll", "command"):
            problems.append(f"envs.{name}.type unknown: {env.get('type')}")
    for r in dom.get("domain_reviewers", []):
        if not (domain_dir() / r.get("prompt", "")).exists():
            problems.append(f"domain reviewer prompt missing: {r.get('prompt')}")
    if not (domain_dir() / "checks.sh").exists():
        problems.append("missing .factory/checks.sh (the deterministic gate)")
    pol = factory_config().get("policy", {})
    if pol.get("auto_merge_max_risk") not in ("none", "low", "medium", "high"):
        problems.append("policy.auto_merge_max_risk must be none|low|medium|high")
    try:
        json.dumps(pipeline())
    except FactoryError as e:
        problems.append(str(e))
    return problems
