from __future__ import annotations

import re
from app.models.schemas import ICPProfile, LeadRecord

TECH_ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "eks": "kubernetes",
    "aws eks": "kubernetes",
    "gke": "kubernetes",
    "gcp gke": "kubernetes",
    "aks": "kubernetes",
    "aws ec2": "aws",
    "ec2": "aws",
    "amazon web services": "aws",
    "gcp": "google cloud",
    "datadog apm": "datadog",
    "datadog ccm": "datadog",
    "tf": "terraform",
    "postgres": "postgresql",
    "py": "python",
}


def _normalize_token(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip().lower())
    return TECH_ALIASES.get(cleaned, cleaned)


def _normalize_stack(stack: list[str]) -> set[str]:
    tokens: set[str] = set()
    for item in stack:
        norm = _normalize_token(item)
        if norm:
            tokens.add(norm)
        # Also include raw lowercase so both "eks" and "kubernetes" can match
        raw_low = item.strip().lower()
        if raw_low:
            tokens.add(raw_low)
    return tokens


def _score_size_fit(emp: int, min_emp: int, max_emp: int) -> float:
    if min_emp <= emp <= max_emp:
        return 1.0
    if emp < min_emp:
        floor = max(1.0, min_emp * 0.5)
        if emp <= floor:
            return 0.0
        return (emp - floor) / max(1.0, min_emp - floor)
    ceil = max_emp * 3.0
    if emp >= ceil:
        return 0.0
    return (ceil - emp) / max(1.0, ceil - max_emp)


def _score_role_fit(role: str, target_roles: list[str]) -> float:
    role_low = role.lower()
    role_words = set(re.findall(r"[a-z0-9]+", role_low))
    best = 0.0
    for target in target_roles:
        t_low = target.lower()
        if t_low in role_low or role_low in t_low:
            return 1.0
        t_words = {w for w in re.findall(r"[a-z0-9]+", t_low) if len(w) > 2}
        if t_words:
            overlap = len(role_words & t_words) / len(t_words)
            best = max(best, overlap)
    return min(1.0, best)


def score_structural_fit(lead: LeadRecord, icp: ICPProfile) -> float:
    """Compute deterministic structural match [0.0, 1.0] across stack, size, and role."""
    lead_stack = _normalize_stack(lead.tech_stack)
    icp_stack = {_normalize_token(t) for t in icp.required_tech_signals if t.strip()}
    if icp_stack:
        stack_overlap = min(1.0, len(lead_stack & icp_stack) / len(icp_stack))
    else:
        stack_overlap = 0.5

    size_fit = _score_size_fit(lead.employee_count, icp.min_employees, icp.max_employees)
    role_fit = _score_role_fit(lead.role, icp.target_roles)

    score = 0.55 * stack_overlap + 0.30 * size_fit + 0.15 * role_fit
    return round(max(0.0, min(1.0, score)), 4)
