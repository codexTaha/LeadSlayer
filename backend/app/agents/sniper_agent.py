from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import SNIPER_SYSTEM_PROMPT
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import (
    SniperBatchLLMResponse,
    SniperLLMResponse,
)
from app.config import settings
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


SNIPER_MICRO_BATCH_SIZE = 4


def verify_evidence_phrase(body: str, raw_phrase: str, cited_signal: str) -> str:
    """
    Guarantees `email_evidence_phrase` resolves as an exact substring inside `body`
    so Improvement #1 UI emerald highlighting never fails.
    """
    phrase = raw_phrase.strip()
    if phrase and phrase in body:
        return phrase

    if phrase:
        idx = body.lower().find(phrase.lower())
        if idx != -1:
            return body[idx : idx + len(phrase)]

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", body) if s.strip()]
    signal_words = {
        w for w in re.findall(r"[a-z0-9]+", cited_signal.lower()) if len(w) > 2
    }
    if sentences:
        best_sentence = max(
            sentences,
            key=lambda s: len(
                signal_words & set(re.findall(r"[a-z0-9]+", s.lower()))
            ),
        )
        return best_sentence
    return body[:80]


async def _prepare_grounding(
    memory_store: HybridMemoryStore | None,
    lead: LeadRecord,
    verdict: SlayerVerdict,
    icp: ICPProfile,
) -> tuple[str, str]:
    if memory_store is not None:
        grounding, _ = await memory_store.get_sniper_grounding(
            lead, verdict.reasoning, icp, top_k=2
        )
        chunks_text = "\n".join(
            f"  - [{c.section}] {c.text}" for c in grounding.top_product_chunks
        )
        matched_summary = (
            grounding.top_product_chunks[0].text
            if grounding.top_product_chunks
            else f"Targeted value prop for {icp.name}"
        )
        return chunks_text, matched_summary

    fallback = f"Targeted GTM value prop for {icp.name} ({', '.join(icp.required_tech_signals)})."
    return f"  - [CORE_PITCH] {fallback}", fallback


async def draft_email_for_lead(
    memory_store: HybridMemoryStore | None,
    lead: LeadRecord,
    verdict: SlayerVerdict,
    icp: ICPProfile,
    client: Any | None = None,
) -> EmailDraft:
    chunks_text, matched_chunk_summary = await _prepare_grounding(
        memory_store, lead, verdict, icp
    )
    prompt = (
        f"SURVIVING LEAD:\n"
        f"- Name: {lead.full_name} ({lead.role} at {lead.company})\n"
        f"- Size/Stage: {lead.employee_count} employees, {lead.funding_stage}\n"
        f"- Tech Stack: {', '.join(lead.tech_stack)}\n"
        f"- Recent Buying Signal: {lead.recent_signal}\n"
        f"- Bio: {lead.bio_snippet}\n"
        f"- Slayer Survival Reason: {verdict.reasoning}\n\n"
        f"MATCHED ICP: {icp.name} (Triggers: {', '.join(icp.buying_triggers)})\n\n"
        f"STAGE 2 RETRIEVED PRODUCT CAPABILITIES:\n{chunks_text}\n"
    )

    genai_client = client or genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    response = await genai_client.aio.models.generate_content(
        model=settings.gemini_brain_model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SNIPER_SYSTEM_PROMPT,
            temperature=0.35,
            response_mime_type="application/json",
            response_schema=SniperLLMResponse,
        ),
    )
    parsed = SniperLLMResponse.model_validate_json(response.text or "{}")
    verified_phrase = verify_evidence_phrase(
        parsed.body, parsed.email_evidence_phrase, parsed.cited_survival_signal
    )

    return EmailDraft(
        lead_id=lead.id,
        recipient_name=lead.full_name,
        recipient_email=lead.email,
        company=lead.company,
        subject=parsed.subject.strip(),
        body=parsed.body.strip(),
        cited_survival_signal=parsed.cited_survival_signal.strip() or lead.recent_signal,
        email_evidence_phrase=verified_phrase,
        matched_product_chunk=matched_chunk_summary,
        personalization_score=parsed.personalization_score,
        approved=True,
        status="DRAFTED",
    )


async def execute_sniper_swarm(
    run_id: str,
    leads: list[LeadRecord],
    icps: list[ICPProfile],
    verdicts: dict[str, SlayerVerdict],
    callbacks: PipelineCallbacks,
    client: Any | None = None,
    batch_size: int = SNIPER_MICRO_BATCH_SIZE,
) -> dict[str, EmailDraft]:
    await callbacks.on_phase(PipelinePhase.SNIPING)
    survivors = [l for l in leads if verdicts.get(l.id) and verdicts[l.id].survived]
    await callbacks.on_log(
        f"[Sniper] Drafting hyper-personalized grounded emails for {len(survivors)} survivors on {settings.gemini_brain_model}..."
    )

    if not survivors:
        return {}

    memory_store = memory_registry.get(run_id)
    icp_by_id = {icp.id: icp for icp in icps}

    batches = [
        survivors[i : i + batch_size]
        for i in range(0, len(survivors), max(1, batch_size))
    ]

    async def _draft_batch(batch: list[LeadRecord]) -> list[EmailDraft]:
        active_key = ""
        if client is None:
            active_key = key_rotator.next_key()
            batch_client = genai.Client(
                api_key=active_key,
                http_options=genai.types.HttpOptions(
                    retry_options=genai.types.HttpRetryOptions(attempts=1)
                ),
            )
        else:
            batch_client = client

        prepared: list[tuple[LeadRecord, str, str]] = []
        lead_blocks: list[str] = []
        for lead in batch:
            verdict = verdicts[lead.id]
            icp = icp_by_id.get(verdict.matched_icp_id or "", icps[0])
            chunks_text, matched_summary = await _prepare_grounding(
                memory_store, lead, verdict, icp
            )
            prepared.append((lead, chunks_text, matched_summary))
            lead_blocks.append(
                f"[lead_id={lead.id}]\n"
                f"  Name: {lead.full_name} ({lead.role} at {lead.company})\n"
                f"  Size/Stage: {lead.employee_count} employees, {lead.funding_stage}\n"
                f"  Stack: {', '.join(lead.tech_stack)}\n"
                f"  Recent Buying Signal: {lead.recent_signal}\n"
                f"  Slayer Survival Reason: {verdict.reasoning}\n"
                f"  Matched ICP: {icp.name}\n"
                f"  Stage 2 Retrieved Capabilities:\n{chunks_text}"
            )

        prompt = (
            f"Draft ONE unique, hyper-personalized email per surviving lead below "
            f"(return all {len(batch)} drafts in `drafts` keyed by `lead_id`):\n\n"
            + "\n\n".join(lead_blocks)
        )
        try:
            response = await batch_client.aio.models.generate_content(
                model=settings.gemini_brain_model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SNIPER_SYSTEM_PROMPT,
                    temperature=0.35,
                    response_mime_type="application/json",
                    response_schema=SniperBatchLLMResponse,
                ),
            )
            if client is None and active_key:
                key_rotator.mark_ok(active_key)
        except Exception as exc:
            if client is None and active_key and ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)):
                key_rotator.mark_throttled(active_key)
            raise
        parsed = SniperBatchLLMResponse.model_validate_json(response.text or "{}")
        by_id = {d.lead_id: d for d in parsed.drafts}

        results: list[EmailDraft] = []
        for lead, _, matched_summary in prepared:
            item = by_id.get(lead.id)
            if item is None:
                # Fallback single call if batch missed one lead_id
                icp = icp_by_id.get(verdicts[lead.id].matched_icp_id or "", icps[0])
                results.append(
                    await draft_email_for_lead(
                        memory_store, lead, verdicts[lead.id], icp, client=batch_client
                    )
                )
                continue
            verified_phrase = verify_evidence_phrase(
                item.body, item.email_evidence_phrase, item.cited_survival_signal
            )
            results.append(
                EmailDraft(
                    lead_id=lead.id,
                    recipient_name=lead.full_name,
                    recipient_email=lead.email,
                    company=lead.company,
                    subject=item.subject.strip(),
                    body=item.body.strip(),
                    cited_survival_signal=item.cited_survival_signal.strip() or lead.recent_signal,
                    email_evidence_phrase=verified_phrase,
                    matched_product_chunk=matched_summary,
                    personalization_score=item.personalization_score,
                    approved=True,
                    status="DRAFTED",
                )
            )
        return results

    executor = GentleAdaptiveExecutor(
        concurrency=2, launch_stagger_s=0.1, max_retries=2, backoff_schedule=(2.0, 5.0)
    )
    emails: dict[str, EmailDraft] = {}
    async for _, batch_drafts in executor.run_stream(batches, _draft_batch):
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        for draft in batch_drafts:
            emails[draft.lead_id] = draft
            await callbacks.on_email(draft)

    await callbacks.on_log(
        f"[Sniper] Drafted {len(emails)} evidence-backed emails ready for dispatch."
    )
    return emails


async def resurrect_single_lead(
    run_id: str,
    lead: LeadRecord,
    old_verdict: SlayerVerdict,
    icp: ICPProfile,
    client: Any | None = None,
) -> tuple[SlayerVerdict, EmailDraft]:
    """Human-in-the-loop override (#4): resurrects a killed lead & runs Sniper live."""
    memory_store = memory_registry.get(run_id)
    new_verdict = old_verdict.model_copy(
        update={
            "survived": True,
            "resurrected_by_user": True,
            "matched_icp_id": icp.id,
            "headline_tag": "RESURRECTED: Founder Override",
        }
    )

    executor = GentleAdaptiveExecutor(concurrency=1, launch_stagger_s=0.0, max_retries=2)
    draft: EmailDraft | None = None

    async def _call(_: int) -> EmailDraft:
        return await draft_email_for_lead(memory_store, lead, new_verdict, icp, client=client)

    async for _, res in executor.run_stream([0], _call):
        draft = res

    assert draft is not None
    return new_verdict, draft


class SniperADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_id: str
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        leads = [LeadRecord.model_validate(item) for item in ctx.session.state["leads"]]
        icps = [ICPProfile.model_validate(item) for item in ctx.session.state["icps"]]
        verdicts = {
            lid: SlayerVerdict.model_validate(raw)
            for lid, raw in ctx.session.state["verdicts"].items()
        }
        emails = await execute_sniper_swarm(
            self.run_id, leads, icps, verdicts, self.callbacks
        )
        emails_dict = {
            lid: d.model_dump(mode="json") for lid, d in emails.items()
        }
        ctx.session.state["emails"] = emails_dict
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[
                    genai.types.Part.from_text(
                        text=f"Sniper drafted {len(emails)} emails"
                    )
                ],
            ),
            actions=EventActions(state_delta={"emails": emails_dict}),
        )
