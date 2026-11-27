"""Merge policy, enforced in code. No agent can talk its way past this."""
from __future__ import annotations

import fnmatch

from . import config, state
from .util import RISK_ORDER


def effective(job: dict) -> dict:
    """Factory-wide policy overlaid with the repo's own (the domain harness may tighten or loosen it)."""
    pol = config.factory_config().get("policy", {})
    proj = config.project(job["project"])
    return {**pol, **config.domain_config(proj).get("policy", {})}


def merge_decision(job: dict, head_sha: str, changed_files: list[str]) -> tuple[str, str]:
    """Return (status, reason) where status is pass | needs_human | fail."""
    pol = effective(job)

    if pol.get("require_gate_on_head", True) and job.get("gate_sha") != head_sha:
        return "fail", f"gate ran on {job.get('gate_sha')} but head is {head_sha}; re-run gate"

    approver = state.latest_results(job, "approve")
    if not approver or any(r.get("status") != "pass" for r in approver):
        return "fail", "approver did not give LGTM"

    if pol.get("require_all_reviewers_pass", True):
        bad = [r.get("agent") for r in state.latest_results(job, "review")
               if r.get("status") not in ("pass", "skip")]
        if bad:
            return "fail", f"reviewers not passing: {bad}"

    if job.get("human_merge_approved"):
        return "pass", "human approved merge"

    max_risk = pol.get("auto_merge_max_risk", "low")
    risk = job.get("risk") or "high"  # unknown risk is treated as high
    if max_risk == "none":
        return "needs_human", "auto-merge is off (policy.auto_merge_max_risk = none); a human approves every merge"
    if RISK_ORDER.get(risk, 2) > RISK_ORDER.get(max_risk, 0):
        return "needs_human", f"risk {risk} exceeds auto-merge limit {max_risk}"

    protected = pol.get("protected_paths", [])
    hits = [f for f in changed_files if any(fnmatch.fnmatch(f, p) for p in protected)]
    if hits:
        return "needs_human", f"protected paths changed: {hits[:10]}"

    return "pass", f"auto-merge allowed (risk {risk} <= {max_risk})"
