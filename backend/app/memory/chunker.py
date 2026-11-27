from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel

from app.models.schemas import MarketAuditResult, StartupInput


class KnowledgeChunk(BaseModel):
    chunk_id: str
    section: Literal["CORE_PITCH", "PAIN_SOLVED", "TECH_CAPABILITY", "PROOF_POINT"]
    text: str


def _split_into_word_chunks(text: str, max_words: int = 115) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return []
    chunks: list[str] = []
    current: list[str] = []
    word_count = 0
    for sentence in sentences:
        s_words = len(sentence.split())
        if current and word_count + s_words > max_words:
            chunks.append(" ".join(current))
            current = [sentence]
            word_count = s_words
        else:
            current.append(sentence)
            word_count += s_words
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_startup_and_audit(
    startup: StartupInput, audit: MarketAuditResult
) -> tuple[list[KnowledgeChunk], list[str]]:
    """Convert StartupInput + MarketAuditResult into focused semantic KnowledgeChunks."""
    chunks: list[KnowledgeChunk] = []
    idx = 1

    core_text = f"{startup.product_name}: {audit.sharpened_value_prop}".strip()
    chunks.append(
        KnowledgeChunk(chunk_id=f"chunk_{idx:02d}", section="CORE_PITCH", text=core_text)
    )
    idx += 1

    if audit.market_reality_summary.strip():
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"chunk_{idx:02d}",
                section="PAIN_SOLVED",
                text=audit.market_reality_summary.strip(),
            )
        )
        idx += 1

    for desc_part in _split_into_word_chunks(startup.description, max_words=115):
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"chunk_{idx:02d}",
                section="TECH_CAPABILITY",
                text=desc_part,
            )
        )
        idx += 1

    for comp in audit.competitor_landscape[:3]:
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"chunk_{idx:02d}",
                section="PROOF_POINT",
                text=(
                    f"Versus {comp.name}: {comp.positioning_weakness}. "
                    f"Best switching trigger: {comp.switching_trigger}."
                ),
            )
        )
        idx += 1

    if not audit.competitor_landscape and audit.founder_blind_spots:
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"chunk_{idx:02d}",
                section="PROOF_POINT",
                text="Key market insight: " + "; ".join(audit.founder_blind_spots[:2]),
            )
        )

    anti_icps = [flag.strip() for flag in audit.anti_icp_red_flags if flag.strip()]
    return chunks, anti_icps
