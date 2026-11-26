import re
from app.models.schemas import ICPProfile, LeadRecord

TECH_ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "eks": "kubernetes",
    "gke": "kubernetes",
    "aks": "kubernetes",
    "aws ec2": "aws",
    "ec2": "aws",
    "aws-ec2": "aws",
    "gcp": "google cloud",
    "datadog apm": "datadog",
    "datadog-apm": "datadog",
    "datadog tracing": "datadog",
    "tf": "terraform",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "kafka broker": "kafka",
}


def normalize_tech_token(tech: str) -> str:
    cleaned = tech.strip().lower()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    return TECH_ALIASES.get(cleaned, cleaned)


def normalize_tech_set(tech_list: list[str]) -> set[str]:
    normalized = set()
    for item in tech_list:
        norm = normalize_tech_token(item)
        normalized.add(norm)
        # Also add individual words if composite
        for sub in re.split(r"[\s/-]+", item.lower()):
            sub_norm = TECH_ALIASES.get(sub, sub)
            if len(sub_norm) > 1:
                normalized.add(sub_norm)
    return normalized


def score_structural_fit(lead: LeadRecord, icp: ICPProfile) -> float:
    """
    Computes deterministic structural fit between a lead and an ICP:
    - Tech Stack Overlap (55% weight)
    - Company Headcount Fit (30% weight with linear decay)
    - Decision Maker Role Match (15% weight)
    Returns: float in range [0.0, 1.0]
    """
    # 1. Tech Stack Overlap (0.55 weight)
    lead_tech = normalize_tech_set(lead.tech_stack)
    icp_tech = normalize_tech_set(icp.required_tech_signals)

    if not icp_tech:
        stack_overlap = 0.5
    else:
        overlap = lead_tech.intersection(icp_tech)
        stack_overlap = min(1.0, len(overlap) / max(1, len(icp_tech)))

    # 2. Company Size Fit (0.30 weight)
    emp = float(lead.employee_count)
    min_emp = float(icp.min_employees)
    max_emp = float(icp.max_employees)

    if min_emp <= emp <= max_emp:
        size_fit = 1.0
    elif emp < min_emp:
        lower_bound = 0.5 * min_emp
        if emp <= lower_bound:
            size_fit = 0.0
        else:
            size_fit = (emp - lower_bound) / max(1.0, (min_emp - lower_bound))
    else:  # emp > max_emp
        upper_bound = 3.0 * max_emp
        if emp >= upper_bound:
            size_fit = 0.0
        else:
            size_fit = (upper_bound - emp) / max(1.0, (upper_bound - max_emp))

    size_fit = max(0.0, min(1.0, size_fit))

    # 3. Role Fit (0.15 weight)
    lead_role_lower = lead.role.strip().lower()
    lead_tokens = set(re.findall(r"\b\w+\b", lead_role_lower))

    role_fit = 0.0
    for target in icp.target_roles:
        target_lower = target.strip().lower()
        if target_lower in lead_role_lower or lead_role_lower in target_lower:
            role_fit = 1.0
            break
        target_tokens = set(re.findall(r"\b\w+\b", target_lower))
        if target_tokens and target_tokens.issubset(lead_tokens):
            role_fit = 1.0
            break
        # Common seniority + function check
        overlap_tokens = target_tokens.intersection(lead_tokens)
        if overlap_tokens:
            partial = len(overlap_tokens) / len(target_tokens)
            role_fit = max(role_fit, partial)

    role_fit = max(0.0, min(1.0, role_fit))

    # Weighted composite score
    total_score = (0.55 * stack_overlap) + (0.30 * size_fit) + (0.15 * role_fit)
    return float(max(0.0, min(1.0, total_score)))
