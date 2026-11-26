import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import build_slayer_system_prompt
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.slayer_agent import normalize_headline, run_slayer_triage
from app.agents.sniper_agent import resurrect_single_lead, verify_and_align_evidence
from app.agents.structured_outputs import _SlayerLLMResponse, _SniperLLMResponse
from app.memory.exceptions import GeminiAPIUnavailableError
from app.memory.vector_store import HybridMatchContext, HybridMemoryStore
from app.models.schemas import (
    ICPProfile,
    LeadRecord,
    ModelId,
    PipelinePhase,
    RejectionCategory,
    SlayerVerdict,
    SlayingLevel,
)


def test_slayer_structured_output_field_order():
    """Verify that _SlayerLLMResponse enforces think-first reasoning before verdict."""
    fields = list(_SlayerLLMResponse.model_fields.keys())
    assert "disqualifier_signals_found" in fields
    assert "tier_triggered" in fields
    assert "survived" in fields
    assert fields.index("disqualifier_signals_found") < fields.index("survived")
    assert fields.index("tier_triggered") < fields.index("survived")


def test_slayer_prompt_tiered_rubric():
    """Verify prompt embeds Tier 1, 2, and 3 correctly based on SlayingLevel."""
    ruthless_prompt = build_slayer_system_prompt(
        SlayingLevel.RUTHLESS,
        anti_icp_red_flags=["3-year Datadog Enterprise lock-in"],
    )
    assert "TIER 1: Hard Blockers" in ruthless_prompt
    assert "TIER 2: ICP & Stack Fit" in ruthless_prompt
    assert "TIER 3: Urgency & Timing Friction" in ruthless_prompt
    assert "RUTHLESS MODE DIRECTIVE" in ruthless_prompt
    assert "3-year Datadog Enterprise lock-in" in ruthless_prompt

    lenient_prompt = build_slayer_system_prompt(SlayingLevel.LENIENT, [])
    assert "LENIENT MODE DIRECTIVE" in lenient_prompt
    assert "Kill ONLY obvious Tier 1 Hard Blockers" in lenient_prompt


def test_sniper_evidence_phrase_alignment():
    """Verify that email_evidence_phrase is strictly aligned as a verbatim substring in body."""
    body = (
        "Hi Sarah, noticed your team recently saw a 3.2x AWS cost spike after migrating "
        "to multi-region Kubernetes. KubeGuard AI stops cost regressions at the PR level."
    )

    # 1. Exact match
    phrase1 = "3.2x AWS cost spike"
    aligned1 = verify_and_align_evidence(body, phrase1, "")
    assert aligned1 in body
    assert aligned1 == phrase1

    # 2. Case difference
    phrase2 = "3.2X AWS COST SPIKE"
    aligned2 = verify_and_align_evidence(body, phrase2, "")
    assert aligned2 in body
    assert aligned2 == "3.2x AWS cost spike"

    # 3. Paraphrased phrase falls back to most relevant sentence
    phrase3 = "massive cloud infrastructure expenditure surge"
    aligned3 = verify_and_align_evidence(body, phrase3, "3.2x AWS cost spike")
    assert aligned3 in body


@pytest.mark.asyncio
async def test_adaptive_executor_shared_cooldown_and_max_retries():
    """Verify executor pauses across workers on 429 and raises GeminiAPIUnavailableError when exhausted."""
    executor = GentleAdaptiveExecutor(concurrency=2, launch_stagger_s=0.01, max_retries=1)

    call_count = 0

    async def failing_worker(item: int):
        nonlocal call_count
        call_count += 1
        raise Exception("429 ResourceExhausted: rate limit exceeded")

    with pytest.raises(GeminiAPIUnavailableError) as exc_info:
        items = [1]
        async for _ in executor.run_stream(items, failing_worker):
            pass

    assert exc_info.value.status_code == 429
    assert call_count == 2  # 1 initial + 1 retry


@pytest.mark.asyncio
async def test_slayer_triage_mocked():
    """Test slayer triage with mocked Gemini client returning verdicts."""
    mock_client = MagicMock()

    lead = LeadRecord(
        id="lead_test_1",
        full_name="Alex River",
        role="CTO",
        company="CloudScale",
        domain="cloudscale.io",
        industry="DevOps",
        employee_count=120,
        funding_stage="Series B",
        tech_stack=["kubernetes", "aws"],
        recent_signal="AWS bill grew 3.2x",
        bio_snippet="CTO scaling cloud platform",
        email="alex@cloudscale.io",
    )

    icp = ICPProfile(
        id="icp_1",
        name="Kubernetes Scale",
        target_roles=["CTO"],
        min_employees=50,
        max_employees=500,
        required_tech_signals=["kubernetes"],
        buying_triggers=["AWS cost spike"],
        instant_disqualifiers=[],
        vector_doc_id="icp_1",
    )

    prior = HybridMatchContext(
        lead_id=lead.id,
        best_icp=icp,
        icp_similarity_score=0.88,
        anti_icp_similarity_score=0.12,
        matched_anti_icp_rule="None",
        structural_match_score=0.92,
        prior_score_100=85,
    )

    slayer_resp = _SlayerLLMResponse(
        disqualifier_signals_found=[],
        tier_triggered="NONE",
        rejection_category=None,
        reasoning="High urgency AWS spike with strong Kubernetes stack fit.",
        survived=True,
        headline_tag="SURVIVED: 3.2x AWS Spike",
        confidence=0.92,
    )

    mock_client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text=slayer_resp.model_dump_json())
    )

    callbacks = MagicMock()
    callbacks.on_phase = AsyncMock()
    callbacks.on_model_call = AsyncMock()
    callbacks.on_log = AsyncMock()
    callbacks.on_verdict = AsyncMock()

    verdicts = await run_slayer_triage(
        leads=[lead],
        priors={lead.id: prior},
        slaying_level=SlayingLevel.RUTHLESS,
        anti_icp_red_flags=["Active layoffs"],
        callbacks=callbacks,
        client=mock_client,
    )

    assert lead.id in verdicts
    v = verdicts[lead.id]
    assert v.survived is True
    assert v.rejection_category is None
    assert v.qualification_score >= 70
    assert "SURVIVED:" in v.headline_tag
    callbacks.on_verdict.assert_awaited_once()


@pytest.mark.asyncio
async def test_resurrect_single_lead():
    """Verify resurrect_single_lead turns killed lead into survived and returns EmailDraft."""
    mock_client = MagicMock()

    sniper_resp = _SniperLLMResponse(
        cited_survival_signal="Infra expansion to 3 regions",
        subject="quick question on k8s cost guardrails",
        body="Hi Sarah, noticed your infra expansion to 3 regions. KubeGuard AI provides automated rightsizing.",
        email_evidence_phrase="infra expansion to 3 regions",
        personalization_score=94,
    )

    mock_client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text=sniper_resp.model_dump_json())
    )

    # Mock embedder for grounding query
    mock_client.aio.models.embed_content = AsyncMock(
        return_value=MagicMock(embeddings=[MagicMock(values=[0.1] * 768)])
    )

    lead = LeadRecord(
        id="lead_killed_1",
        full_name="Sarah Connor",
        role="VP Engineering",
        company="Cyberdyne",
        domain="cyberdyne.com",
        industry="AI",
        employee_count=100,
        funding_stage="Series B",
        tech_stack=["kubernetes", "aws"],
        recent_signal="Infra expansion to 3 regions",
        bio_snippet="VP Engineering",
        email="sarah@cyberdyne.com",
    )

    old_verdict = SlayerVerdict(
        lead_id=lead.id,
        survived=False,
        resurrected_by_user=False,
        rejection_category=RejectionCategory.NO_URGENCY_SIGNAL,
        headline_tag="KILLED: No Urgent Pain",
        reasoning="Good stack but lacked urgent signal.",
        matched_icp_id="icp_1",
        icp_similarity_score=0.75,
        anti_icp_similarity_score=0.20,
        structural_match_score=0.85,
        qualification_score=50,
        confidence=0.80,
        slaying_level_applied=SlayingLevel.RUTHLESS,
        latency_ms=120,
    )

    icp = ICPProfile(
        id="icp_1",
        name="Platform Scale",
        target_roles=["VP Engineering"],
        min_employees=50,
        max_employees=500,
        required_tech_signals=["kubernetes"],
        buying_triggers=["Infra expansion"],
        instant_disqualifiers=[],
        vector_doc_id="icp_1",
    )

    new_verdict, draft = await resurrect_single_lead(
        run_id="test_run",
        lead=lead,
        old_verdict=old_verdict,
        icp=icp,
        client=mock_client,
    )

    assert new_verdict.survived is True
    assert new_verdict.resurrected_by_user is True
    assert new_verdict.rejection_category is None
    assert "RESURRECTED:" in new_verdict.headline_tag
    assert draft.lead_id == lead.id
    assert draft.email_evidence_phrase in draft.body
    assert draft.recipient_email == lead.email
