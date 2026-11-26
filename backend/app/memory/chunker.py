from typing import Literal
from pydantic import BaseModel

from app.models.schemas import MarketAuditResult, StartupInput


class KnowledgeChunk(BaseModel):
    chunk_id: str
    section: Literal["CORE_PITCH", "PAIN_SOLVED", "TECH_CAPABILITY", "PROOF_POINT"]
    text: str


def _limit_words(text: str, max_words: int = 120) -> str:
    words = text.strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def chunk_startup_and_audit(
    startup: StartupInput,
    audit: MarketAuditResult,
) -> tuple[list[KnowledgeChunk], list[str]]:
    """
    Splits startup input and audited market reality into 4–8 crisp, self-contained
    product capability chunks (<= 120 words each) for sniper grounding, along with
    the anti-ICP red flag rules for dual-polarity retrieval.
    """
    chunks: list[KnowledgeChunk] = []

    # 1. CORE_PITCH: Sharpened Value Proposition
    pitch_text = f"{startup.product_name}: {audit.sharpened_value_prop}"
    chunks.append(
        KnowledgeChunk(
            chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_core_pitch",
            section="CORE_PITCH",
            text=_limit_words(pitch_text, 120),
        )
    )

    # 2. PAIN_SOLVED: Market Reality & Urgency
    pain_text = f"Market problem solved: {audit.market_reality_summary}"
    chunks.append(
        KnowledgeChunk(
            chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_pain_solved",
            section="PAIN_SOLVED",
            text=_limit_words(pain_text, 120),
        )
    )

    # 3. TECH_CAPABILITY: Extracted from startup.description
    # Split description into 1-3 capability chunks if multi-sentence
    raw_desc = startup.description.strip()
    sentences = [s.strip() for s in raw_desc.replace("\n", ". ").split(". ") if s.strip()]

    if len(sentences) <= 2:
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_tech_cap_1",
                section="TECH_CAPABILITY",
                text=_limit_words(raw_desc, 120),
            )
        )
    else:
        mid = len(sentences) // 2
        part1 = ". ".join(sentences[:mid]) + "."
        part2 = ". ".join(sentences[mid:]) + ("" if sentences[-1].endswith(".") else ".")
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_tech_cap_1",
                section="TECH_CAPABILITY",
                text=_limit_words(part1, 120),
            )
        )
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_tech_cap_2",
                section="TECH_CAPABILITY",
                text=_limit_words(part2, 120),
            )
        )

    # 4. PROOF_POINT: Countering founder blind spots & market objections
    blind_spots_summary = "; ".join(audit.founder_blind_spots[:3])
    proof_text = f"Key market differentiation & blind spots addressed: {blind_spots_summary}"
    chunks.append(
        KnowledgeChunk(
            chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_proof_point",
            section="PROOF_POINT",
            text=_limit_words(proof_text, 120),
        )
    )

    # If assumption gaps or competitor landscape exist, add additional targeted proof point
    if audit.assumption_gaps:
        gap_fixes = "; ".join([g.strategic_fix for g in audit.assumption_gaps[:2]])
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{startup.product_name.lower().replace(' ', '_')}_strategic_fix",
                section="PROOF_POINT",
                text=_limit_words(f"Strategic positioning vs competitors: {gap_fixes}", 120),
            )
        )

    return chunks, audit.anti_icp_red_flags
