import numpy as np
from pydantic import BaseModel, Field

from app.memory.chunker import KnowledgeChunk, chunk_startup_and_audit
from app.memory.embedder import GeminiEmbedder
from app.memory.structural_matcher import score_structural_fit
from app.models.schemas import ICPProfile, LeadRecord, MarketAuditResult, StartupInput


def serialize_icp(icp: ICPProfile) -> str:
    return (
        f"Target ICP: {icp.name}. Roles: {', '.join(icp.target_roles)}. "
        f"Company size: {icp.min_employees}-{icp.max_employees}. "
        f"Required stack: {', '.join(icp.required_tech_signals)}. "
        f"Buying triggers: {'; '.join(icp.buying_triggers)}."
    )


def serialize_lead(lead: LeadRecord) -> str:
    return (
        f"Role: {lead.role} at {lead.company} ({lead.industry}, {lead.employee_count} employees, "
        f"{lead.funding_stage}). Stack: {', '.join(lead.tech_stack)}. "
        f"Recent signal: {lead.recent_signal}. Bio: {lead.bio_snippet}"
    )


class HybridMatchContext(BaseModel):
    lead_id: str
    best_icp: ICPProfile
    icp_similarity_score: float = Field(ge=0.0, le=1.0)
    anti_icp_similarity_score: float = Field(ge=0.0, le=1.0)
    matched_anti_icp_rule: str
    structural_match_score: float = Field(ge=0.0, le=1.0)
    prior_score_100: int = Field(ge=0, le=100)


class SniperGrounding(BaseModel):
    lead_id: str
    top_product_chunks: list[KnowledgeChunk]
    matched_icp: ICPProfile


class HybridMemoryStore:
    """
    Dual-Polarity In-Memory Vector Store for LeadSlayer AI.
    Maintains L2-normalized NumPy float32 embeddings for product chunks, ICPs,
    and Anti-ICPs, and evaluates incoming leads with combined semantic + structural priors.
    """

    def __init__(self, embedder: GeminiEmbedder | None = None):
        self.embedder = embedder or GeminiEmbedder()

        # Knowledge state
        self.startup: StartupInput | None = None
        self.audit: MarketAuditResult | None = None
        self.icps: list[ICPProfile] = []
        self.anti_icps: list[str] = []
        self.product_chunks: list[KnowledgeChunk] = []

        # Vector matrices (N, 768) float32
        self.chunk_matrix: np.ndarray = np.zeros((0, 768), dtype=np.float32)
        self.icp_matrix: np.ndarray = np.zeros((0, 768), dtype=np.float32)
        self.anti_icp_matrix: np.ndarray = np.zeros((0, 768), dtype=np.float32)

    async def index_knowledge(
        self,
        startup: StartupInput,
        audit: MarketAuditResult,
        icps: list[ICPProfile],
    ) -> int:
        """
        Embeds and indexes product chunks, 3 generated ICPs, and anti-ICP red flags.
        Returns the total number of live API batch calls made.
        """
        self.startup = startup
        self.audit = audit
        self.icps = icps

        product_chunks, anti_icp_rules = chunk_startup_and_audit(startup, audit)
        self.product_chunks = product_chunks
        self.anti_icps = anti_icp_rules

        # 1. Product chunks
        chunk_texts = [c.text for c in product_chunks]
        c_mat, c_calls = await self.embedder.embed_texts(chunk_texts, task_type="RETRIEVAL_DOCUMENT")
        self.chunk_matrix = c_mat

        # 2. ICPs
        icp_texts = [serialize_icp(icp) for icp in icps]
        i_mat, i_calls = await self.embedder.embed_texts(icp_texts, task_type="RETRIEVAL_DOCUMENT")
        self.icp_matrix = i_mat

        # 3. Anti-ICPs
        anti_texts = [f"Anti-ICP Red Flag: {flag}" for flag in anti_icp_rules]
        if anti_texts:
            a_mat, a_calls = await self.embedder.embed_texts(anti_texts, task_type="RETRIEVAL_DOCUMENT")
            self.anti_icp_matrix = a_mat
        else:
            self.anti_icp_matrix = np.zeros((0, self.embedder.output_dimensionality), dtype=np.float32)
            a_calls = 0

        return c_calls + i_calls + a_calls

    async def index_and_score_leads(
        self,
        leads: list[LeadRecord],
    ) -> tuple[dict[str, HybridMatchContext], int]:
        """
        Batch-embeds all leads and computes Dual-Polarity Hybrid Priors:
        raw_hybrid = 0.60 * icp_sim + 0.25 * struct_score - 0.15 * anti_icp_sim
        prior_score_100 = round(clip(raw_hybrid, 0, 1) * 100)
        Returns:
            (priors_by_lead_id, live_api_calls_count)
        """
        if not leads:
            return {}, 0

        lead_texts = [serialize_lead(lead) for lead in leads]
        lead_matrix, api_calls = await self.embedder.embed_texts(lead_texts, task_type="SEMANTIC_SIMILARITY")

        priors: dict[str, HybridMatchContext] = {}

        # 1. Dot product against ICPs (N_leads, N_icps)
        if len(self.icp_matrix) > 0:
            icp_sims = np.clip(lead_matrix @ self.icp_matrix.T, 0.0, 1.0)
        else:
            icp_sims = np.zeros((len(leads), 1), dtype=np.float32)

        # 2. Dot product against Anti-ICPs (N_leads, N_anti)
        if len(self.anti_icp_matrix) > 0:
            anti_sims = np.clip(lead_matrix @ self.anti_icp_matrix.T, 0.0, 1.0)
        else:
            anti_sims = np.zeros((len(leads), 0), dtype=np.float32)

        for i, lead in enumerate(leads):
            # Best ICP match
            if len(self.icps) > 0:
                best_icp_idx = int(np.argmax(icp_sims[i]))
                best_icp = self.icps[best_icp_idx]
                icp_sim = float(icp_sims[i, best_icp_idx])
            else:
                best_icp = ICPProfile(
                    id="icp_fallback",
                    name="Default ICP",
                    target_roles=[],
                    min_employees=1,
                    max_employees=1000,
                    required_tech_signals=[],
                    buying_triggers=[],
                    instant_disqualifiers=[],
                    vector_doc_id="fallback",
                )
                icp_sim = 0.5

            # Anti-ICP match (strongest negative signal)
            if anti_sims.shape[1] > 0:
                worst_anti_idx = int(np.argmax(anti_sims[i]))
                anti_sim = float(anti_sims[i, worst_anti_idx])
                anti_rule = self.anti_icps[worst_anti_idx]
            else:
                anti_sim = 0.0
                anti_rule = "None"

            # Structural match
            struct_score = score_structural_fit(lead, best_icp)

            # Dual-polarity fusion formula
            raw_hybrid = (0.60 * icp_sim) + (0.25 * struct_score) - (0.15 * anti_sim)
            prior_100 = int(round(float(np.clip(raw_hybrid, 0.0, 1.0)) * 100))

            priors[lead.id] = HybridMatchContext(
                lead_id=lead.id,
                best_icp=best_icp,
                icp_similarity_score=round(icp_sim, 4),
                anti_icp_similarity_score=round(anti_sim, 4),
                matched_anti_icp_rule=anti_rule,
                structural_match_score=round(struct_score, 4),
                prior_score_100=prior_100,
            )

        return priors, api_calls

    async def get_sniper_grounding(
        self,
        lead: LeadRecord,
        survival_reason: str,
        matched_icp: ICPProfile,
        top_k: int = 2,
    ) -> tuple[SniperGrounding, int]:
        """
        Retrieves the top-k most relevant product capability chunks from memory
        to ground the Sniper Agent's cold email drafting.
        """
        query_text = (
            f"Grounding query for {lead.role} at {lead.company}. "
            f"Tech stack: {', '.join(lead.tech_stack)}. Signal: {lead.recent_signal}. "
            f"Reason survived: {survival_reason}"
        )

        query_mat, api_calls = await self.embedder.embed_texts([query_text], task_type="SEMANTIC_SIMILARITY")

        if len(self.product_chunks) == 0:
            return SniperGrounding(lead_id=lead.id, top_product_chunks=[], matched_icp=matched_icp), api_calls

        scores = (self.chunk_matrix @ query_mat.T).flatten()
        actual_k = min(top_k, len(self.product_chunks))
        top_indices = np.argsort(scores)[::-1][:actual_k]

        top_chunks = [self.product_chunks[int(idx)] for idx in top_indices]

        return (
            SniperGrounding(
                lead_id=lead.id,
                top_product_chunks=top_chunks,
                matched_icp=matched_icp,
            ),
            api_calls,
        )
