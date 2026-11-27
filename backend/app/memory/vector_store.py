from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from app.memory.chunker import KnowledgeChunk, chunk_startup_and_audit
from app.memory.embedder import GeminiEmbedder
from app.memory.structural_matcher import score_structural_fit
from app.models.schemas import ICPProfile, LeadRecord, MarketAuditResult, StartupInput


def serialize_icp(icp: ICPProfile) -> str:
    return (
        f"Target ICP: {icp.name}. "
        f"Roles: {', '.join(icp.target_roles)}. "
        f"Company size: {icp.min_employees}-{icp.max_employees}. "
        f"Required stack: {', '.join(icp.required_tech_signals)}. "
        f"Buying triggers: {'; '.join(icp.buying_triggers)}."
    )


def serialize_lead(lead: LeadRecord) -> str:
    return (
        f"Role: {lead.role} at {lead.company} "
        f"({lead.industry}, {lead.employee_count} employees, {lead.funding_stage}). "
        f"Stack: {', '.join(lead.tech_stack)}. "
        f"Recent signal: {lead.recent_signal}. "
        f"Bio: {lead.bio_snippet}"
    )


class HybridMatchContext(BaseModel):
    lead_id: str
    best_icp: ICPProfile
    icp_similarity_score: float = Field(ge=0.0, le=1.0)
    anti_icp_similarity_score: float = Field(ge=0.0, le=1.0)
    matched_anti_icp_rule: str = ""
    structural_match_score: float = Field(ge=0.0, le=1.0)
    prior_score_100: int = Field(ge=0, le=100)


class SniperGrounding(BaseModel):
    lead_id: str
    top_product_chunks: list[KnowledgeChunk]
    matched_icp: ICPProfile


class HybridMemoryStore:
    """In-memory L2-normalized NumPy vector index with Dual-Polarity Hybrid scoring."""

    def __init__(self, embedder: GeminiEmbedder | None = None) -> None:
        self._embedder = embedder or GeminiEmbedder()
        self._product_chunks: list[KnowledgeChunk] = []
        self._product_matrix: np.ndarray | None = None
        self._icps: list[ICPProfile] = []
        self._icp_matrix: np.ndarray | None = None
        self._anti_icps: list[str] = []
        self._anti_icp_matrix: np.ndarray | None = None
        self._leads: list[LeadRecord] = []
        self._lead_matrix: np.ndarray | None = None

    async def index_knowledge(
        self,
        startup: StartupInput,
        audit: MarketAuditResult,
        icps: list[ICPProfile],
    ) -> int:
        chunks, anti_icps = chunk_startup_and_audit(startup, audit)
        self._product_chunks = chunks
        self._icps = list(icps)
        self._anti_icps = anti_icps

        all_docs = (
            [c.text for c in chunks]
            + [serialize_icp(icp) for icp in icps]
            + anti_icps
        )
        matrix, api_calls = await self._embedder.embed_texts(
            all_docs, task_type="RETRIEVAL_DOCUMENT"
        )

        n_prod = len(chunks)
        n_icp = len(icps)
        self._product_matrix = matrix[:n_prod]
        self._icp_matrix = matrix[n_prod : n_prod + n_icp]
        self._anti_icp_matrix = matrix[n_prod + n_icp :]
        return api_calls

    async def index_and_score_leads(
        self, leads: list[LeadRecord]
    ) -> tuple[dict[str, HybridMatchContext], int]:
        if self._icp_matrix is None or len(self._icps) == 0:
            raise RuntimeError("index_knowledge() must be called before scoring leads.")

        self._leads = list(leads)
        if not leads:
            return {}, 0

        lead_texts = [serialize_lead(lead) for lead in leads]
        lead_matrix, api_calls = await self._embedder.embed_texts(
            lead_texts, task_type="SEMANTIC_SIMILARITY"
        )
        self._lead_matrix = lead_matrix

        icp_sims = lead_matrix @ self._icp_matrix.T  # (N, 3)
        best_icp_indices = np.argmax(icp_sims, axis=1)
        max_icp_sims = np.clip(np.max(icp_sims, axis=1), 0.0, 1.0)

        if self._anti_icp_matrix is not None and self._anti_icp_matrix.shape[0] > 0:
            anti_sims = lead_matrix @ self._anti_icp_matrix.T
            best_anti_indices = np.argmax(anti_sims, axis=1)
            max_anti_sims = np.clip(np.max(anti_sims, axis=1), 0.0, 1.0)
        else:
            best_anti_indices = np.zeros(len(leads), dtype=int)
            max_anti_sims = np.zeros(len(leads), dtype=np.float32)

        contexts: dict[str, HybridMatchContext] = {}
        for i, lead in enumerate(leads):
            best_icp = self._icps[int(best_icp_indices[i])]
            icp_sim = float(max_icp_sims[i])
            anti_sim = float(max_anti_sims[i])
            matched_anti = (
                self._anti_icps[int(best_anti_indices[i])]
                if self._anti_icps
                else ""
            )
            struct_score = score_structural_fit(lead, best_icp)
            raw_hybrid = 0.60 * icp_sim + 0.25 * struct_score - 0.15 * anti_sim
            prior_100 = int(round(float(np.clip(raw_hybrid, 0.0, 1.0)) * 100))

            contexts[lead.id] = HybridMatchContext(
                lead_id=lead.id,
                best_icp=best_icp,
                icp_similarity_score=round(icp_sim, 4),
                anti_icp_similarity_score=round(anti_sim, 4),
                matched_anti_icp_rule=matched_anti,
                structural_match_score=struct_score,
                prior_score_100=prior_100,
            )

        return contexts, api_calls

    async def get_sniper_grounding(
        self,
        lead: LeadRecord,
        survival_reason: str,
        matched_icp: ICPProfile,
        top_k: int = 2,
    ) -> tuple[SniperGrounding, int]:
        if self._product_matrix is None or not self._product_chunks:
            return (
                SniperGrounding(
                    lead_id=lead.id,
                    top_product_chunks=[],
                    matched_icp=matched_icp,
                ),
                0,
            )

        query = (
            f"{lead.role} at {lead.company} ({', '.join(lead.tech_stack)}): "
            f"{lead.recent_signal} | {survival_reason}"
        )
        query_mat, api_calls = await self._embedder.embed_texts(
            [query], task_type="RETRIEVAL_QUERY"
        )
        sims = (self._product_matrix @ query_mat[0]).tolist()
        ranked_indices = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
        top_chunks = [self._product_chunks[i] for i in ranked_indices[:top_k]]
        return (
            SniperGrounding(
                lead_id=lead.id,
                top_product_chunks=top_chunks,
                matched_icp=matched_icp,
            ),
            api_calls,
        )
