"""Load base-harness config (factory/config.json) and domain-harness config (<repo>/.factory/config.json)."""
from __future__ import annotations

from pathlib import Path

from .util import CONFIG_PATH, FACTORY_DIR, FactoryError, load_json

DOMAIN_DIRNAME = ".factory"

DOMAIN_DEFAULTS = {
    "tracker": {"type": "local"},
    "vcs": {"type": "local", "base_branch": "main"},
    "envs": {"dev": {"type": "none"}, "stg": {"type": "none"}},
    "areas": {"backend": ["backend/"], "frontend": ["frontend/"]},
    "domain_reviewers": [],
}


def factory_config() -> dict:
    path = CONFIG_PATH
    if not path.exists():
        raise FactoryError("factory/config.json not found. Run `bin/factory init` first.")
    return load_json(path)


def pipeline() -> dict:
    return load_json(FACTORY_DIR / "pipeline.json")


def project(name: str) -> dict:
    for p in factory_config().get("projects", []):
        if p["name"] == name:
            return p
    raise FactoryError(f"unknown project: {name}")


def domain_dir(proj: dict) -> Path:
    return Path(proj["repo_path"]) / DOMAIN_DIRNAME


def domain_config(proj: dict) -> dict:
    cfg = load_json(domain_dir(proj) / "config.json", default={})
    merged = {**DOMAIN_DEFAULTS, **cfg}
    for key in ("tracker", "vcs"):
        merged[key] = {**DOMAIN_DEFAULTS[key], **cfg.get(key, {})}
    return merged


def model_for(agent: str) -> str:
    models = factory_config().get("models", {})
    return models.get(agent, models.get("default", "sonnet"))
