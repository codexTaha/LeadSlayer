from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agents.prompts import build_slayer_system_prompt
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.slayer_agent import execute_slayer_swarm
from app.agents.sniper_agent import resurrect_single_lead, verify_evidence_phrase
from app.agents.structured_outputs import SlayerLLMResponse
from app.memory.exceptions import GeminiAPIUnavailableError
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    ICPProfile,
    MarketAuditResult,
    RejectionCategory,
    SlayerVerdict,
    SlayingLevel,
)
from app.services.lead_loader import load_default_startup, load_preset_leads


class _DummyCallbacks:
    def __init__(self) -> None:
        self.verdicts: list[SlayerVerdict] = []
        self.models: list[str] = []
        self.logs: list[str] = []

    async def on_phase(self, phase) -> None:
        pass

    async def on_log(self, message: str) -> None:
        self.logs.append(message)

    async def on_model_call(self, model_id) -> None:
        self.models.append(model_id.value)

    async def on_audit(self, audit) -> None:
        pass

    async def on_icps(self, icps) -> None:
        pass

    async def on_leads_loaded(self, leads) -> None:
        pass

    async def on_hunter_report(self, report) -> None:
        pass

    async def on_verdict(self, verdict: SlayerVerdict) -> None:
        self.verdicts.append(verdict)

    async def on_email(self, draft) -> None:
        pass

    async def on_mcp_tool_call(self, record) -> None:
        pass


class _FakeAsyncGenAIClient:
    def __init__(self, mode: str = "slayer") -> None:
        self._mode = mode

    @property
    def aio(self) -> "_FakeAsyncGenAIClient":
        return self

    @property
    def models(self) -> "_FakeAsyncGenAIClient":
        return self

    async def generate_content(self, *, model: str, contents: str, config=None):
        if self._mode == "slayer":
            verdicts = []
            for lid, is_survivor in (("lead_01", False), ("lead_04", True)):
                if lid in contents:
                    verdicts.append(
                        {
                            "lead_id": lid,
                            "disqualifier_signals_found": [] if is_survivor else ["Datadog 3-year contract"],
                            "tier_triggered": "NONE" if is_survivor else "TIER_1_HARD",
                            "rejection_category": None if is_survivor else "COMPETITOR_LOCK_IN",
                            "reasoning": (
                                "AWS bill jumped 3.2x on EKS with active urgency."
                                if is_survivor
                                else "Locked into 3-year Datadog Cloud Cost deal."
                            ),
                            "survived": is_survivor,
                            "headline_tag": "3.2x AWS Spike" if is_survivor else "Datadog Lock-In",
                            "confidence": 0.94,
                        }
                    )
            return SimpleNamespace(text=json.dumps({"verdicts": verdicts}))

        payload = {
            "cited_survival_signal": "Signed 3-year Datadog expansion",
            "subject": "eks cluster costs at relayflow",
            "body": "Hi Marcus, saw your team signed a 3-year Datadog expansion recently. If spot-node autoscaling still causes billing surprises, KubeGuard catches them early.",
            "email_evidence_phrase": "Signed A 3-Year Datadog Expansion",  # intentional casing mismatch
            "personalization_score": 89,
        }
        return SimpleNamespace(text=json.dumps(payload))


def test_slayer_schema_orders_reasoning_before_verdict() -> None:
    keys = list(SlayerLLMResponse.model_fields.keys())
    assert keys.index("disqualifier_signals_found") < keys.index("survived")
    assert keys.index("reasoning") < keys.index("survived")


def test_slayer_prompt_respects_levels_and_injects_anti_icp() -> None:
    flags = ["Signed Datadog multi-year deal", "Under 15 employees"]
    ruthless_prompt = build_slayer_system_prompt(SlayingLevel.RUTHLESS, flags)
    lenient_prompt = build_slayer_system_prompt(SlayingLevel.LENIENT, flags)

    assert "Signed Datadog multi-year deal" in ruthless_prompt
    assert "KILL all TIER_1_HARD, all TIER_2_ICP_FIT, AND all TIER_3_FRICTION" in ruthless_prompt
    assert "LET THEM SURVIVE" in lenient_prompt


async def test_gentle_executor_cooldown_and_unavailable_error() -> None:
    executor = GentleAdaptiveExecutor(
        concurrency=2,
        launch_stagger_s=0.0,
        max_retries=1,
        backoff_schedule=(0.02,),
    )
    attempts = 0

    async def _always_429(item: int) -> int:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(GeminiAPIUnavailableError) as exc_info:
        async for _ in executor.run_stream([1], _always_429):
            pass

    assert attempts == 2  # initial + 1 retry
    assert exc_info.value.status_code == 429


async def test_gentle_executor_fails_fast_on_daily_quota() -> None:
    executor = GentleAdaptiveExecutor(concurrency=1, launch_stagger_s=0.0, max_retries=2)
    attempts = 0

    async def _daily_limit(item: int) -> int:
        nonlocal attempts
        attempts += 1
        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier retryDelay: 22937s"
        )

    with pytest.raises(GeminiAPIUnavailableError) as exc_info:
        async for _ in executor.run_stream([1], _daily_limit):
            pass

    assert attempts == 1  # Fast-failed immediately with 0 wasted sleeps!
    assert exc_info.value.status_code == 429
    assert "daily" in exc_info.value.user_message.lower()


async def test_slayer_swarm_execution_and_score_fusion() -> None:
    startup = load_default_startup()
    leads = [l for l in load_preset_leads() if l.id in ("lead_01", "lead_04")]
    audit = MarketAuditResult(
        market_reality_summary="EKS teams bleed GPU spend.",
        founder_blind_spots=["Not all cloud teams run K8s."],
        sharpened_value_prop="Cut EKS waste 40% without code changes.",
        anti_icp_red_flags=["Datadog lock-in"],
        market_readiness_score=85,
    )
    icp = ICPProfile(
        id="icp_1",
        name="Series B EKS CTO",
        target_roles=["CTO"],
        min_employees=40,
        max_employees=300,
        required_tech_signals=["AWS", "EKS"],
        buying_triggers=["AWS bill spike"],
        instant_disqualifiers=["Datadog"],
        vector_doc_id="icp_1",
    )
    priors = {
        lead.id: HybridMatchContext(
            lead_id=lead.id,
            best_icp=icp,
            icp_similarity_score=0.82,
            anti_icp_similarity_score=0.20 if lead.id == "lead_04" else 0.85,
            structural_match_score=0.90,
            prior_score_100=68 if lead.id == "lead_04" else 55,
        )
        for lead in leads
    }
    callbacks = _DummyCallbacks()
    verdicts = await execute_slayer_swarm(
        startup,
        audit,
        leads,
        priors,
        callbacks,
        client=_FakeAsyncGenAIClient(mode="slayer"),
    )

    assert len(callbacks.verdicts) == 2
    assert verdicts["lead_04"].survived is True
    assert verdicts["lead_04"].headline_tag.startswith("SURVIVED:")
    assert verdicts["lead_04"].qualification_score >= 65
    assert verdicts["lead_01"].survived is False
    assert verdicts["lead_01"].rejection_category == RejectionCategory.COMPETITOR_LOCK_IN
    assert verdicts["lead_01"].qualification_score <= 62


def test_evidence_phrase_verifier_recovers_exact_substring() -> None:
    body = "Hi Elena, noticed your AWS bill jumped 3.2x in 60 days after launching RAG inference."
    resolved = verify_evidence_phrase(
        body,
        "AWS BILL JUMPED 3.2X IN 60 DAYS",
        "AWS bill jumped 3.2x in 60 days",
    )
    assert resolved in body
    assert resolved == "AWS bill jumped 3.2x in 60 days"


async def test_resurrect_single_lead_flips_verdict_and_grounds_email() -> None:
    lead = load_preset_leads()[0]  # lead_01 Marcus Vance
    icp = ICPProfile(
        id="icp_1",
        name="Series B EKS CTO",
        target_roles=["VP of Engineering", "CTO"],
        min_employees=40,
        max_employees=300,
        required_tech_signals=["AWS", "EKS"],
        buying_triggers=["AWS bill spike"],
        instant_disqualifiers=[],
        vector_doc_id="icp_1",
    )
    old_verdict = SlayerVerdict(
        lead_id=lead.id,
        survived=False,
        rejection_category=RejectionCategory.COMPETITOR_LOCK_IN,
        headline_tag="KILLED: Datadog Lock-In",
        reasoning="Datadog contract",
        icp_similarity_score=0.75,
        anti_icp_similarity_score=0.80,
        structural_match_score=0.85,
        qualification_score=32,
        confidence=0.92,
        slaying_level_applied=SlayingLevel.RUTHLESS,
        latency_ms=120,
    )

    new_verdict, draft = await resurrect_single_lead(
        "nonexistent_run_ok",
        lead,
        old_verdict,
        icp,
        client=_FakeAsyncGenAIClient(mode="sniper"),
    )
    assert new_verdict.survived is True
    assert new_verdict.resurrected_by_user is True
    assert draft.email_evidence_phrase in draft.body


def test_url_intel_extraction_and_domain_filtering() -> None:
    from app.agents.hunter_agent import _is_directory_or_self_domain, _normalize_root_domain
    from app.services.url_fetcher import detect_tech_signals, extract_emails_from_html

    html = (
        '<script src="https://cdn.shopify.com/s/files/app.js"></script>'
        '<script src="https://static.klaviyo.com/onsite/js/klaviyo.js"></script>'
        '<a href="mailto:hello@velvetglow.com">Contact</a>'
        '<span>ops@sentry.io</span>'
    )
    emails = extract_emails_from_html(html, expected_domain="velvetglow.com")
    tech = detect_tech_signals(html)
    assert emails == ["hello@velvetglow.com"]
    assert "Shopify" in tech
    assert "Klaviyo" in tech

    own = _normalize_root_domain("https://www.orbixpackaging.com/boxes")
    assert own == "orbixpackaging.com"
    assert _is_directory_or_self_domain("orbixpackaging.com", own) is True
    assert _is_directory_or_self_domain("linkedin.com", own) is True
    assert _is_directory_or_self_domain("velvetglow.com", own) is False


async def test_hunter_autonomous_discovery_emits_verified_leads(monkeypatch) -> None:
    import numpy as np
    from app.agents import hunter_agent
    from app.harvey_bridge.research import HarveyCompanyDossier
    from app.memory.cache import BoundedTTLEmbeddingCache
    from app.memory.embedder import GeminiEmbedder
    from app.memory.registry import memory_registry
    from app.memory.vector_store import HybridMemoryStore
    from app.models.schemas import StartupInput

    class _FakeDiscoveryClient:
        @property
        def aio(self):
            return self

        @property
        def models(self):
            return self

        async def generate_content(self, *, model: str, contents: str, config=None):
            if "HuntQueriesOutput" in str(getattr(config, "response_schema", "")):
                return SimpleNamespace(
                    text=json.dumps(
                        {
                            "hunt_queries": [
                                {
                                    "source": "Google Search",
                                    "query_string": '"custom boxes" cosmetics DTC brand',
                                    "signal_target": "Retail packaging launch",
                                }
                            ]
                        }
                    )
                )
            if "DiscoveredLeadBatch" in str(getattr(config, "response_schema", "")):
                is_li = "site:linkedin.com/in" in contents
                if is_li:
                    return SimpleNamespace(
                        text=json.dumps(
                            {
                                "candidates": [
                                    {
                                        "full_name": "Maya Lin",
                                        "role": "VP Operations",
                                        "company": "Velvet Glow",
                                        "domain": "velvetglow.com",
                                        "industry": "Cosmetics",
                                        "employee_count": 45,
                                        "funding_stage": "Series A",
                                        "tech_stack": ["Shopify"],
                                        "recent_signal": "LinkedIn post about holiday kit fulfillment",
                                        "bio_snippet": "Scaling retail packaging.",
                                        "email_guess": "",
                                        "linkedin_url": "https://www.linkedin.com/in/maya-lin-vg",
                                    },
                                    {
                                        "full_name": "Elena Vance",
                                        "role": "Head of Supply Chain",
                                        "company": "PureBotanicals",
                                        "domain": "purebotanicals.io",
                                        "industry": "Skincare",
                                        "employee_count": 60,
                                        "funding_stage": "Seed",
                                        "tech_stack": ["Shopify"],
                                        "recent_signal": "Posted about sustainable FSC packaging",
                                        "bio_snippet": "Clean beauty ops leader.",
                                        "email_guess": "",
                                        "linkedin_url": "https://www.linkedin.com/in/elena-vance-pb",
                                    },
                                ]
                            }
                        )
                    )
                return SimpleNamespace(
                    text=json.dumps(
                        {
                            "candidates": [
                                {
                                    "full_name": "Operations Leadership",
                                    "role": "VP Operations",
                                    "company": "Velvet Glow",
                                    "domain": "https://www.velvetglow.com",
                                    "industry": "Cosmetics",
                                    "employee_count": 45,
                                    "funding_stage": "Series A",
                                    "tech_stack": ["Shopify"],
                                    "recent_signal": "Launching holiday gift kits",
                                    "bio_snippet": "Clean skincare brand scaling retail.",
                                    "email_guess": "",
                                    "linkedin_url": "",
                                },
                                {
                                    "full_name": "Directory Spam",
                                    "role": "Listing",
                                    "company": "LinkedIn",
                                    "domain": "linkedin.com",
                                    "industry": "Tech",
                                    "employee_count": 1000,
                                    "funding_stage": "Public",
                                    "tech_stack": [],
                                    "recent_signal": "Directory",
                                    "bio_snippet": "Should be filtered",
                                    "email_guess": "",
                                    "linkedin_url": "",
                                },
                            ]
                        }
                    )
                )
            return SimpleNamespace(
                text=f"Grounded summary for prompt: {contents[:80]}"
            )

    async def _fake_harvey_research(
        domain: str, candidate_name: str = "", candidate_role: str = "", timeout_s: float = 3.5
    ) -> HarveyCompanyDossier:
        return HarveyCompanyDossier(
            reachable=True,
            summary=f"Title: {domain} | Clean DTC Storefront",
            emails=[f"press@{domain}"],
            resolved_email=f"maya@{domain}" if "velvetglow" in domain else f"elena@{domain}",
            email_status="guess",
            mx_provider="google",
            email_pattern="{f}",
            tech_signals=["Klaviyo"],
            decision_makers=[{"first_name": "Maya", "last_name": "Lin", "title": "VP Operations"}],
            ats_open_roles=["Packaging Coordinator · Operations · posted 2026-11-15"],
            ats_board_label="Greenhouse",
        )

    class _FakeSyncEmbedClient:
        @property
        def models(self):
            return self

        def embed_content(self, *, model: str, contents: list, config=None):
            vec = (np.ones(8, dtype=np.float32) / np.sqrt(8.0)).tolist()
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=vec) for _ in contents]
            )

    monkeypatch.setattr(hunter_agent, "research_company_with_harvey", _fake_harvey_research)

    run_id = "test_auto_disc_run"
    embedder = GeminiEmbedder(
        api_key="test",
        dim=8,
        cache=BoundedTTLEmbeddingCache(dim=8),
        client=_FakeSyncEmbedClient(),
    )
    store = HybridMemoryStore(embedder=embedder)
    monkeypatch.setattr(memory_registry, "get_or_create", lambda rid: store)

    # Test combined AI_SEARCH + LINKEDIN_SEARCH deduplicating velvetglow.com & keeping LinkedIn person + URL
    startup = StartupInput(
        product_name="Orbix Packaging",
        product_url="https://orbixpackaging.com",
        description="Custom wholesale folding cartons and rigid boxes for DTC brands.",
        founder_assumptions="Any e-commerce brand buys boxes.",
        lead_sources=["AI_SEARCH", "LINKEDIN_SEARCH"],
        auto_discover_leads=True,
        target_lead_count=10,
    )
    icp = ICPProfile(
        id="icp_1",
        name="DTC Beauty Brands",
        target_roles=["VP Operations"],
        min_employees=20,
        max_employees=200,
        required_tech_signals=["Shopify"],
        buying_triggers=["Holiday kit launch"],
        instant_disqualifiers=[],
        vector_doc_id="icp_1",
    )
    await store.index_knowledge(
        startup,
        MarketAuditResult(
            market_reality_summary="Retail brands need rigid boxes.",
            founder_blind_spots=["Not solo Etsy shops."],
            sharpened_value_prop="Fast-turnaround custom rigid boxes.",
            anti_icp_red_flags=["Solo hobby shop"],
            market_readiness_score=80,
        ),
        [icp],
    )

    cb = _DummyCallbacks()
    loaded: list = []

    async def _cap_leads(leads):
        loaded.extend(leads)

    cb.on_leads_loaded = _cap_leads  # type: ignore[method-assign]

    leads_out, priors, report = await hunter_agent.execute_hunter_swarm(
        run_id,
        [],
        [icp],
        cb,
        startup=startup,
        client=_FakeDiscoveryClient(),
    )
    assert len(leads_out) == 2
    assert len(loaded) == 2
    vg = next(l for l in leads_out if l.domain == "velvetglow.com")
    assert vg.full_name == "Maya Lin"  # Merged LinkedIn person over generic AI Search label
    assert vg.linkedin_url == "https://www.linkedin.com/in/maya-lin-vg"
    assert vg.source_channel == "AI Search + LinkedIn"
    assert vg.email == "maya@velvetglow.com"
    assert vg.mx_provider == "google"
    assert "Greenhouse" in vg.recent_signal
    assert "Klaviyo" in vg.tech_stack
    assert report.autonomous_discovered_leads == 2
    assert report.url_fetches_succeeded == 2
    assert vg.id in priors


async def test_harvey_pre_send_gate_and_smtp_dispatch(monkeypatch) -> None:
    from app.config import settings
    from app.harvey_bridge import dispatcher
    from app.models.schemas import EmailDraft, LeadRecord

    drafts = {
        "l1": EmailDraft(
            lead_id="l1",
            recipient_name="Maya Lin",
            recipient_email="maya@velvetglow.com",
            company="Velvet Glow",
            subject="holiday cartons at velvet glow",
            body="Saw Velvet Glow is hiring a Packaging Coordinator on Greenhouse. We deliver custom FSC boxes with low MOQs in 10 days. Worth a quick look?",
            cited_survival_signal="Hiring Packaging Coordinator",
            email_evidence_phrase="hiring a Packaging Coordinator on Greenhouse",
            matched_product_chunk="Custom low-MOQ rigid boxes",
            personalization_score=91,
        ),
        "l2": EmailDraft(
            lead_id="l2",
            recipient_name="Blocked Lead",
            recipient_email="bob@competitor.example",
            company="Competitor Inc",
            subject="hope this finds you well",
            body="Hi {{first_name}}, hope this email finds you well! Let us revolutionize your boxes.",
            cited_survival_signal="Hiring",
            email_evidence_phrase="revolutionize your boxes",
            matched_product_chunk="Boxes",
            personalization_score=70,
        ),
    }
    leads = {
        "l1": LeadRecord(
            id="l1",
            full_name="Maya Lin",
            role="VP Operations",
            company="Velvet Glow",
            domain="velvetglow.com",
            industry="Cosmetics",
            employee_count=45,
            funding_stage="Series A",
            email="maya@velvetglow.com",
            email_status="guess",
            mx_provider="google",
        ),
        "l2": LeadRecord(
            id="l2",
            full_name="Blocked Lead",
            role="CTO",
            company="Competitor Inc",
            domain="competitor.example",
            industry="Packaging",
            employee_count=100,
            funding_stage="Series B",
            email="bob@competitor.example",
            email_status="verified",
            mx_provider="google",
        ),
    }

    sent_payloads: list[tuple[str, str]] = []

    class _FakeSmtpProvider:
        def __init__(self, cfg, env) -> None:
            pass

        def is_configured(self) -> bool:
            return True

        async def send_email(self, to_email: str, subject: str, body: str, thread_ref="", in_reply_to=""):
            sent_payloads.append((to_email, subject))
            return SimpleNamespace(ok=True, message_id="<test-msg@leadslayer>", error="")

    monkeypatch.setattr(dispatcher, "SmtpImapProvider", _FakeSmtpProvider)
    monkeypatch.setattr(settings, "do_not_contact_domains", "competitor.example")

    resp, any_sent = await dispatcher.dispatch_emails_via_harvey(
        emails=drafts,
        leads_by_id=leads,
        lead_ids=["l1", "l2"],
        delivery_mode="HARVEY_SMTP",
        product_name="Orbix Packaging",
    )
    assert any_sent is True
    assert resp.dispatched_count == 1
    assert resp.blocked_count == 1
    assert sent_payloads == [("maya@velvetglow.com", "holiday cartons at velvet glow")]
    r1 = next(r for r in resp.receipts if r.lead_id == "l1")
    r2 = next(r for r in resp.receipts if r.lead_id == "l2")
    assert r1.status == "SENT"
    assert r1.message_id == "<test-msg@leadslayer>"
    assert r2.status == "BLOCKED"
    assert any("do-not-contact" in reason for reason in r2.gate_reasons)


async def test_key_rotator_search_isolation_and_encapsulated_web_index(monkeypatch) -> None:
    from app.agents.key_rotator import KeyRotator
    from app.harvey_bridge import web_index
    from app.config import settings

    rot = KeyRotator(["k1", "k2"])
    rot.mark_search_throttled("k1")
    # Search cooldown must NOT quarantine k1 for standard LLM/embedding inference
    assert rot.next_key() == "k1"
    assert rot.next_search_key() == "k2"
    rot.mark_search_throttled("k2")
    assert rot.next_search_key() is None

    monkeypatch.setattr(settings, "serper_api_key", "test-serp-key")
    assert web_index.has_live_web_index() is True

    class _FakeResp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "organic": [
                    {
                        "title": "Acme Cloud Infra - Engineering",
                        "link": "https://acmecloud.io/platform",
                        "snippet": "Scaling Kubernetes workloads across AWS EKS clusters.",
                    }
                ]
            }

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers=None, json=None):
            assert json["num"] <= 10
            return _FakeResp()

    monkeypatch.setattr(web_index.httpx, "AsyncClient", _FakeAsyncClient)
    notes, urls = await web_index.query_live_web_index(["kubernetes eks saas"], num_per_query=25)
    assert urls == ["https://acmecloud.io/platform"]
    assert "Acme Cloud Infra" in notes
    assert "serper" not in notes.lower()
