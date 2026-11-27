from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.memory.cache import BoundedTTLEmbeddingCache, build_cache_key
from app.memory.embedder import GeminiEmbedder
from app.memory.exceptions import GeminiAPIUnavailableError
from app.memory.registry import MemoryRegistry
from app.memory.vector_store import HybridMemoryStore
from app.models.schemas import (
    CompetitorInsight,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
)
from app.services.lead_loader import load_default_startup, load_preset_leads


class _FakeEmbedClient:
    """Deterministic semantic vector stub based on domain keywords for unit tests."""

    def __init__(self, dim: int = 16, fail_with: Exception | None = None) -> None:
        self.dim = dim
        self.fail_with = fail_with
        self.calls = 0

    @property
    def models(self) -> "_FakeEmbedClient":
        return self

    def embed_content(self, *, model: str, contents: list, config=None):
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with

        embeddings = []
        for item in contents:
            if isinstance(item, str):
                text = item
            else:
                text = " ".join(
                    p.text for p in (getattr(item, "parts", None) or []) if getattr(p, "text", None)
                )
            low = text.lower()
            vec = np.zeros(self.dim, dtype=np.float32)
            # Semantic axes: [0]=k8s/eks/aws, [1]=cost/spike/finops, [2]=datadog/lock-in, [3]=layoffs/freeze
            if any(w in low for w in ("kubernetes", "eks", "gke", "k8s", "cto", "platform")):
                vec[0] += 1.0
            if any(w in low for w in ("cost", "spike", "finops", "autoscaling", "bill", "guardrail")):
                vec[1] += 1.0
            if any(w in low for w in ("datadog", "cast.ai", "kubecost", "lock-in", "contract")):
                vec[2] += 1.0
            if any(w in low for w in ("layoff", "freeze", "laid off", "moratorium")):
                vec[3] += 1.0
            if np.linalg.norm(vec) == 0:
                vec[4] = 1.0
            embeddings.append(SimpleNamespace(values=vec.tolist()))
        return SimpleNamespace(embeddings=embeddings)


async def test_cache_ttl_expiry_and_lru_cap(tmp_path: Path) -> None:
    cache_file = tmp_path / ".emb_cache.json"
    cache = BoundedTTLEmbeddingCache(
        cache_path=cache_file,
        dim=4,
        ttl_seconds=1,
        max_entries=2,
    )

    k1 = build_cache_key("m", 4, "RETRIEVAL_DOCUMENT", "alpha")
    k2 = build_cache_key("m", 4, "RETRIEVAL_DOCUMENT", "beta")
    k3 = build_cache_key("m", 4, "RETRIEVAL_DOCUMENT", "gamma")

    await cache.put_many({k1: np.ones(4), k2: np.ones(4) * 2})
    assert cache_file.exists()
    assert not cache_file.with_suffix(".json.tmp").exists()

    # Touch k1 so k2 is least recently used, then insert k3 -> k2 evicted
    hits, misses = await cache.get_many([k1])
    assert k1 in hits and misses == []
    await cache.put_many({k3: np.ones(4) * 3})
    assert cache.size == 2
    hits2, misses2 = await cache.get_many([k1, k2, k3])
    assert k2 not in hits2 and misses2 == [1]

    # Wait > 1s TTL -> expired
    await asyncio.sleep(1.1)
    hits3, misses3 = await cache.get_many([k1, k3])
    assert hits3 == {}
    assert misses3 == [0, 1]


async def test_embedder_raises_unavailable_on_429_without_fake_vectors(tmp_path: Path) -> None:
    cache = BoundedTTLEmbeddingCache(cache_path=tmp_path / ".emb_cache.json", dim=16)
    failing_client = _FakeEmbedClient(
        dim=16, fail_with=RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
    )
    embedder = GeminiEmbedder(
        api_key="test-key",
        dim=16,
        max_retries=0,  # instant failure check without 1.5s test wait
        cache=cache,
        client=failing_client,
    )

    with pytest.raises(GeminiAPIUnavailableError) as exc_info:
        await embedder.embed_texts(["never fake this vector"], task_type="RETRIEVAL_DOCUMENT")

    assert exc_info.value.status_code == 429
    assert "limit" in exc_info.value.user_message.lower()


async def test_dual_polarity_scoring_and_sniper_grounding(tmp_path: Path) -> None:
    cache = BoundedTTLEmbeddingCache(cache_path=tmp_path / ".emb_cache.json", dim=16)
    fake_client = _FakeEmbedClient(dim=16)
    embedder = GeminiEmbedder(
        api_key="test-key", dim=16, batch_size=25, cache=cache, client=fake_client
    )
    store = HybridMemoryStore(embedder=embedder)

    startup = load_default_startup()
    audit = MarketAuditResult(
        market_reality_summary="AWS EKS teams suffer unpredictable pod autoscaling cost spikes.",
        founder_blind_spots=["Small serverless teams don't need K8s FinOps."],
        sharpened_value_prop="Predicts AWS EKS cost spikes 48h early with zero code changes.",
        anti_icp_red_flags=[
            "Multi-year Datadog Cloud Cost Management contract lock-in",
            "Active layoffs or CFO vendor freeze",
        ],
        market_readiness_score=88,
        competitor_landscape=[
            CompetitorInsight(
                name="Datadog CCM",
                positioning_weakness="Reactive billing dashboards only",
                switching_trigger="Unexpected EKS spike",
            )
        ],
    )
    icp = ICPProfile(
        id="icp_1",
        name="Series B EKS CTO",
        target_roles=["CTO", "VP of Engineering"],
        min_employees=40,
        max_employees=300,
        required_tech_signals=["AWS", "Kubernetes", "Terraform"],
        buying_triggers=["AWS bill spike"],
        instant_disqualifiers=["Datadog contract"],
        vector_doc_id="icp_1",
    )

    await store.index_knowledge(startup, audit, [icp])

    leads = load_preset_leads()
    # lead_04 is Elena Rostova (Golden Survivor), lead_01 is Datadog Lock-In, lead_03 is Layoffs
    contexts, calls = await store.index_and_score_leads(leads)
    assert calls == 2  # 50 leads / batch_size=25 -> 2 batched calls!

    assert contexts["lead_04"].prior_score_100 > contexts["lead_01"].prior_score_100
    assert contexts["lead_04"].prior_score_100 > contexts["lead_03"].prior_score_100
    assert contexts["lead_01"].anti_icp_similarity_score > contexts["lead_04"].anti_icp_similarity_score

    # Second run on identical leads hits 6h cache with 0 API calls
    _, second_calls = await store.index_and_score_leads(leads)
    assert second_calls == 0

    elena = next(l for l in leads if l.id == "lead_04")
    grounding, _ = await store.get_sniper_grounding(
        elena, "AWS bill jumped 3.2x on EKS", icp, top_k=2
    )
    assert len(grounding.top_product_chunks) == 2


def test_memory_registry_isolation_and_eviction() -> None:
    registry = MemoryRegistry(max_runs=2, ttl_seconds=60)
    s1 = registry.get_or_create("run_1")
    s2 = registry.get_or_create("run_2")
    assert s1 is not s2

    s3 = registry.get_or_create("run_3")
    assert s3 is not None
    assert registry.get("run_1") is None
    assert registry.get("run_2") is s2


def test_structural_matcher_aliases_and_size_decay() -> None:
    from app.memory.structural_matcher import score_structural_fit

    icp = ICPProfile(
        id="icp_1",
        name="EKS CTO",
        target_roles=["CTO", "VP of Engineering"],
        min_employees=40,
        max_employees=300,
        required_tech_signals=["Kubernetes", "AWS", "Terraform"],
        buying_triggers=[],
        instant_disqualifiers=[],
        vector_doc_id="icp_1",
    )
    strong = LeadRecord(
        id="l1",
        full_name="A",
        role="CTO",
        company="GoodCo",
        domain="good.io",
        industry="AI",
        employee_count=100,
        funding_stage="Series B",
        tech_stack=["EKS", "AWS EC2", "tf"],
        email="a@good.io",
    )
    weak = LeadRecord(
        id="l2",
        full_name="B",
        role="Brand Designer",
        company="TinyCo",
        domain="tiny.io",
        industry="Design",
        employee_count=4,
        funding_stage="Pre-Seed",
        tech_stack=["Figma"],
        email="b@tiny.io",
    )
    assert score_structural_fit(strong, icp) >= 0.95
    assert score_structural_fit(weak, icp) < 0.15
