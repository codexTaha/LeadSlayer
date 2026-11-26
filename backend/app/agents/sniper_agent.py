import re
from typing import Any
from google import genai
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import SNIPER_SYSTEM_PROMPT
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import _SniperLLMResponse
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.memory.registry import memory_registry
from app.memory.vector_store import HybridMemoryStore
from app.models.schemas import (
    EmailDraft,
    ICPProfile,
    LeadRecord,
    ModelId,
    PipelinePhase,
    SlayerVerdict,
)


def verify_and_align_evidence(body: str, candidate_phrase: str, signal_fallback: str) -> str:
    """
    Guarantees that email_evidence_phrase is a verbatim substring of body.
    Falls back to the most relevant sentence in body if the LLM paraphrased the phrase.
    """
    if candidate_phrase and candidate_phrase in body:
        return candidate_phrase

    # Case-insensitive substring match
    if candidate_phrase:
        lower_body = body.lower()
        lower_cand = candidate_phrase.strip().lower()
        idx = lower_body.find(lower_cand)
        if idx != -1:
            return body[idx : idx + len(candidate_phrase.strip())]

    # Sentence fallback based on token overlap
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    if not sentences:
        return body[: min(60, len(body))]

    tokens = set(re.findall(r"\b\w{3,}\b", f"{candidate_phrase} {signal_fallback}".lower()))
    best_sent = sentences[0]
    best_overlap = -1
    for sent in sentences:
        sent_tokens = set(re.findall(r"\b\w{3,}\b", sent.lower()))
        overlap = len(tokens.intersection(sent_tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best_sent = sent

    return best_sent


async def generate_single_email(
    lead: LeadRecord,
    verdict_reasoning: str,
    matched_icp: ICPProfile,
    memory_store: HybridMemoryStore,
    client: genai.Client,
    brain_model_id: str = "gemini-4-hydrogen",
) -> EmailDraft:
    """Drafts an evidence-backed email for a single qualified or resurrected lead."""
    grounding, _ = await memory_store.get_sniper_grounding(
        lead=lead,
        survival_reason=verdict_reasoning,
        matched_icp=matched_icp,
        top_k=2,
    )

    chunks_text = "\n\n".join([f"[{c.section}]: {c.text}" for c in grounding.top_product_chunks])
    if not chunks_text:
        chunks_text = "Core Product: Autonomous zero-risk infrastructure optimization."

    prompt = (
        f"RECIPIENT LEAD:\n"
        f"Name: {lead.full_name}\n"
        f"Role: {lead.role}\n"
        f"Company: {lead.company} ({lead.domain})\n"
        f"Tech Stack: {', '.join(lead.tech_stack)}\n"
        f"Recent Signal: {lead.recent_signal}\n"
        f"Survival Reason: {verdict_reasoning}\n\n"
        f"MATCHED ICP:\n{matched_icp.name} ({', '.join(matched_icp.target_roles)})\n\n"
        f"RETRIEVED PRODUCT CAPABILITIES FROM MEMORY:\n{chunks_text}\n"
    )

    config = types.GenerateContentConfig(
        system_instruction=SNIPER_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_SniperLLMResponse,
        temperature=0.3,
    )

    resp = await client.aio.models.generate_content(
        model=brain_model_id,
        contents=[prompt],
        config=config,
    )
    if not resp.text:
        raise GeminiAPIUnavailableError(
            user_message=f"Gemini Sniper failed to draft email for {lead.company}.",
            raw_error="No text in generate_content response",
        )

    llm_resp = _SniperLLMResponse.model_validate_json(resp.text)

    # Enforce verbatim substring guarantee
    aligned_evidence = verify_and_align_evidence(
        body=llm_resp.body,
        candidate_phrase=llm_resp.email_evidence_phrase,
        signal_fallback=lead.recent_signal,
    )

    matched_chunk_repr = grounding.top_product_chunks[0].text if grounding.top_product_chunks else "Core capability"

    return EmailDraft(
        lead_id=lead.id,
        recipient_name=lead.full_name,
        recipient_email=lead.email,
        company=lead.company,
        subject=llm_resp.subject,
        body=llm_resp.body,
        cited_survival_signal=llm_resp.cited_survival_signal or lead.recent_signal,
        email_evidence_phrase=aligned_evidence,
        matched_product_chunk=matched_chunk_repr,
        personalization_score=llm_resp.personalization_score,
        approved=True,
        status="DRAFTED",
    )


async def run_sniper_drafting(
    surviving_leads: list[LeadRecord],
    verdicts: dict[str, SlayerVerdict],
    icps_map: dict[str, ICPProfile],
    memory_store: HybridMemoryStore,
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
    brain_model_id: str = "gemini-4-hydrogen",
) -> dict[str, EmailDraft]:
    """Drafts personalized evidence-backed cold emails for all surviving leads."""
    if callbacks:
        await callbacks.on_phase(PipelinePhase.SNIPING)
        await callbacks.on_log(
            f"Sniper Agent drafting precision emails for {len(surviving_leads)} surviving leads using {brain_model_id}..."
        )

    cli = client or genai.Client(api_key=settings.gemini_api_key)
    executor = GentleAdaptiveExecutor(concurrency=4, launch_stagger_s=0.1)

    emails: dict[str, EmailDraft] = {}

    async def _sniper_worker(lead: LeadRecord) -> EmailDraft:
        verdict = verdicts.get(lead.id)
        reasoning = verdict.reasoning if verdict else lead.recent_signal
        icp_id = verdict.matched_icp_id if verdict else "icp_1"
        matched_icp = icps_map.get(icp_id) or (list(icps_map.values())[0] if icps_map else ICPProfile(
            id="icp_1",
            name="General",
            target_roles=[],
            min_employees=1,
            max_employees=1000,
            required_tech_signals=[],
            buying_triggers=[],
            instant_disqualifiers=[],
            vector_doc_id="icp_1",
        ))
        draft = await generate_single_email(
            lead=lead,
            verdict_reasoning=reasoning,
            matched_icp=matched_icp,
            memory_store=memory_store,
            client=cli,
            brain_model_id=brain_model_id,
        )
        return draft

    async for lead, draft in executor.run_stream(surviving_leads, _sniper_worker):
        emails[lead.id] = draft
        if callbacks:
            await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
            await callbacks.on_email(draft)
            await callbacks.on_log(f"Sniper drafted email for {lead.full_name} at {lead.company} (Subject: '{draft.subject}')")

    return emails


async def resurrect_single_lead(
    run_id: str,
    lead: LeadRecord,
    old_verdict: SlayerVerdict,
    icp: ICPProfile,
    client: genai.Client | None = None,
    brain_model_id: str = "gemini-4-hydrogen",
) -> tuple[SlayerVerdict, EmailDraft]:
    """
    On-demand resurrection: flips a killed lead to SURVIVED, resurrects in memory,
    and drafts a personalized email using gemini-4-hydrogen.
    """
    cli = client or genai.Client(api_key=settings.gemini_api_key)
    store = memory_registry.get(run_id)
    if store is None:
        from app.memory.embedder import GeminiEmbedder
        store = HybridMemoryStore(embedder=GeminiEmbedder(client=cli))

    draft = await generate_single_email(
        lead=lead,
        verdict_reasoning=f"Resurrected by founder: {lead.recent_signal}",
        matched_icp=icp,
        memory_store=store,
        client=cli,
        brain_model_id=brain_model_id,
    )

    new_verdict = SlayerVerdict(
        lead_id=lead.id,
        survived=True,
        resurrected_by_user=True,
        rejection_category=None,
        headline_tag=f"RESURRECTED: {lead.company}"[:30],
        reasoning=f"Resurrected by user. Grounded in signal: {lead.recent_signal}",
        matched_icp_id=icp.id,
        icp_similarity_score=old_verdict.icp_similarity_score,
        anti_icp_similarity_score=old_verdict.anti_icp_similarity_score,
        structural_match_score=old_verdict.structural_match_score,
        qualification_score=max(75, old_verdict.qualification_score),
        confidence=0.90,
        slaying_level_applied=old_verdict.slaying_level_applied,
        latency_ms=old_verdict.latency_ms,
        model_used=ModelId.GEMINI_4_HYDROGEN,
    )

    return new_verdict, draft


class SniperAgent(BaseAgent):
    """Google ADK BaseAgent wrapper for Sniper Agent."""

    callbacks: Any = None
    client: Any = None
    memory_store: Any = None
    brain_model_id: str = "gemini-4-hydrogen"

    async def _run_async_impl(self, ctx: InvocationContext):
        leads_data = ctx.session.state.get("leads", [])
        leads_map = {
            l.id: l if isinstance(l, LeadRecord) else LeadRecord.model_validate(l)
            for l in leads_data
        }
        verdicts_raw = ctx.session.state.get("verdicts", {})
        verdicts = {
            k: v if isinstance(v, SlayerVerdict) else SlayerVerdict.model_validate(v)
            for k, v in verdicts_raw.items()
        }
        icps_raw = ctx.session.state.get("icps", [])
        icps_map = {
            (icp.id if isinstance(icp, ICPProfile) else icp["id"]): (
                icp if isinstance(icp, ICPProfile) else ICPProfile.model_validate(icp)
            )
            for icp in icps_raw
        }

        surviving_leads = [leads_map[k] for k, v in verdicts.items() if v.survived and k in leads_map]

        emails = await run_sniper_drafting(
            surviving_leads=surviving_leads,
            verdicts=verdicts,
            icps_map=icps_map,
            memory_store=self.memory_store,
            callbacks=self.callbacks,
            client=self.client,
            brain_model_id=self.brain_model_id,
        )

        ctx.session.state["emails"] = {k: v.model_dump() for k, v in emails.items()}
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"emails": {k: v.model_dump() for k, v in emails.items()}}
            ),
        )
