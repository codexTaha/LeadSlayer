import asyncio
import json
from pathlib import Path
import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.memory.cache import BoundedTTLEmbeddingCache
from app.memory.chunker import chunk_startup_and_audit
from app.memory.embedder import GeminiEmbedder
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.memory.registry import MemoryRegistry
from app.memory.structural_matcher import score_structural_fit
from app.memory.vector_store import HybridMemoryStore
from app.models.schemas import (
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    StartupInput,
)


@pytest.mark.asyncio
async def test_cache_ttl(tmp_path: Path):
    """Test that entries expire after ttl_seconds and get evicted on retrieval."""
    cache_file = tmp_path / "test_cache_ttl.json"
    cache = BoundedTTLEmbeddingCache(cache_path=cache_file, ttl_seconds=1, dim=4)

    key = "test_key_1"
    vec = [0.1, 0.2, 0.3, 0.4]

    await cache.put_many({key: vec}, flush=True)
    hits = await cache.get_many([key])
    assert key in hits
    assert hits[key] == vec

    # Sleep past TTL
    await asyncio.sleep(1.1)
    hits_after = await cache.get_many([key])
    assert key not in hits_after


@pytest.mark.asyncio
async def test_cache_lru_eviction(tmp_path: Path):
    """Test that cache enforces max_entries and evicts oldest LRU entry."""
    cache_file = tmp_path / "test_cache_lru.json"
    cache = BoundedTTLEmbeddingCache(cache_path=cache_file, max_entries=3, dim=4)

    entries = {
        "k1": [0.1, 0.1, 0.1, 0.1],
        "k2": [0.2, 0.2, 0.2, 0.2],
        "k3": [0.3, 0.3, 0.3, 0.3],
    }
    await cache.put_many(entries, flush=True)

    # Touch k1 so k2 becomes the oldest
    await cache.get_many(["k1"])

    # Insert k4, should evict k2
    await cache.put_many({"k4": [0.4, 0.4, 0.4, 0.4]}, flush=True)

    hits = await cache.get_many(["k1", "k2", "k3", "k4"])
    assert "k1" in hits
    assert "k3" in hits
    assert "k4" in hits
    assert "k2" not in hits


@pytest.mark.asyncio
async def test_atomic_flush(tmp_path: Path):
    """Test that atomic flush writes clean JSON and does not leave temporary files."""
    cache_file = tmp_path / "test_atomic.json"
    cache = BoundedTTLEmbeddingCache(cache_path=cache_file, dim=4)

    await cache.put_many({"k_atomic": [1.0, 0.0, 0.0, 0.0]}, flush=True)

    assert cache_file.exists()
    assert not cache_file.with_suffix(".tmp").exists()

    with open(cache_file, "r") as f:
        data = json.load(f)
    assert data["version"] == 1
    assert data["dim"] == 4
    assert "k_atomic" in data["entries"]


@pytest.mark.asyncio
async def test_embedder_retries_and_raises_unavailable(tmp_path: Path):
    """Test that embedder raises GeminiAPIUnavailableError after retries on transient errors."""
    cache = BoundedTTLEmbeddingCache(cache_path=tmp_path / "cache.json", dim=768)

    mock_client = MagicMock()
    # Simulate 429 quota exhaustion on all calls
    mock_client.aio.models.embed_content = AsyncMock(
        side_effect=Exception("429 ResourceExhausted: Quota exceeded")
    )

    embedder = GeminiEmbedder(
        client=mock_client,
        cache=cache,
        max_retries=1,
    )

    with pytest.raises(GeminiAPIUnavailableError) as exc_info:
        await embedder.embed_texts(["Kubernetes autoscaling"], task_type="RETRIEVAL_DOCUMENT")

    assert exc_info.value.status_code == 429
    assert "limit reached" in exc_info.value.user_message.lower()
    assert mock_client.aio.models.embed_content.call_count == 2  # initial + 1 retry


def test_structural_matcher_tech_and_size():
    """Verify structural matcher tech alias normalization, size decay, and role matching."""
    icp = ICPProfile(
        id="icp_1",
        name="Mid-Market Kubernetes Platform",
        target_roles=["CTO", "VP of Engineering", "Head of Platform"],
        min_employees=50,
        max_employees=500,
        required_tech_signals=["kubernetes", "aws", "terraform"],
        buying_triggers=["Scaling infra", "Cloud bill spike"],
        instant_disqualifiers=["On-prem mainframe"],
        vector_doc_id="doc_icp_1",
    )

    # Perfect lead: aliases k8s -> kubernetes, ec2 -> aws, tf -> terraform
    perfect_lead = LeadRecord(
        id="lead_1",
        full_name="Sarah Connor",
        role="VP Engineering",
        company="Skynet Systems",
        domain="skynet.io",
        industry="DevTools",
        employee_count=150,
        funding_stage="Series B",
        tech_stack=["k8s", "aws ec2", "tf"],
        recent_signal="Infra bill jumped 3x",
        bio_snippet="Engineering leader building scalable infra",
        email="sarah@skynet.io",
    )

    score_perfect = score_structural_fit(perfect_lead, icp)
    assert score_perfect >= 0.95

    # Poor lead: no stack match, tiny headcount, irrelevant role
    poor_lead = LeadRecord(
        id="lead_2",
        full_name="Bob Smith",
        role="Graphic Designer",
        company="Small Shop",
        domain="small.com",
        industry="Retail",
        employee_count=5,
        funding_stage="Bootstrapped",
        tech_stack=["wordpress", "photoshop"],
        recent_signal="Hiring designer",
        bio_snippet="Creative artist",
        email="bob@small.com",
    )

    score_poor = score_structural_fit(poor_lead, icp)
    assert score_poor < 0.20


@pytest.mark.asyncio
async def test_dual_polarity_scoring_golden_vs_bad(tmp_path: Path):
    """
    Verify Dual-Polarity retrieval scores a golden Kubernetes Series B lead strictly higher
    than a Datadog-locked or layoff lead.
    """
    cache = BoundedTTLEmbeddingCache(cache_path=tmp_path / "cache.json", dim=768)

    # Synthetic normalized vectors
    # v_icp = [1, 0, 0, ...]
    # v_anti = [0, 1, 0, ...]
    v_icp = np.zeros(768, dtype=np.float32)
    v_icp[0] = 1.0

    v_anti = np.zeros(768, dtype=np.float32)
    v_anti[1] = 1.0

    # Golden lead is aligned with v_icp
    v_golden = np.zeros(768, dtype=np.float32)
    v_golden[0] = 0.95
    v_golden[2] = 0.31
    v_golden = v_golden / np.linalg.norm(v_golden)

    # Bad lead is aligned with v_anti
    v_bad = np.zeros(768, dtype=np.float32)
    v_bad[1] = 0.95
    v_bad[2] = 0.31
    v_bad = v_bad / np.linalg.norm(v_bad)

    # Mock Gemini embedder
    mock_client = MagicMock()

    async def mock_embed(*args, contents=None, **kwargs):
        # Return mock embeddings matching query strings
        embeddings = []
        for item in contents:
            text = item.parts[0].text if hasattr(item, "parts") and item.parts else str(item)
            if "Target ICP" in text:
                embeddings.append(MagicMock(values=v_icp.tolist()))
            elif "Anti-ICP" in text:
                embeddings.append(MagicMock(values=v_anti.tolist()))
            elif "Skynet" in text:
                embeddings.append(MagicMock(values=v_golden.tolist()))
            elif "LockedCo" in text:
                embeddings.append(MagicMock(values=v_bad.tolist()))
            else:
                # default chunk vector
                embeddings.append(MagicMock(values=v_icp.tolist()))
        return MagicMock(embeddings=embeddings)

    mock_client.aio.models.embed_content = mock_embed
    embedder = GeminiEmbedder(client=mock_client, cache=cache)
    store = HybridMemoryStore(embedder=embedder)

    startup = StartupInput(
        product_name="KubeGuard AI",
        description="Autonomous Kubernetes cost optimization agent that eliminates cloud waste.",
        founder_assumptions="Every engineering team wants autonomous pod rightsizing.",
    )
    audit = MarketAuditResult(
        market_reality_summary="Teams fear autonomous changes breaking production without guardrails.",
        founder_blind_spots=["Ignored rollback guarantees"],
        sharpened_value_prop="Zero-risk Kubernetes cost guardrails with instant rollbacks.",
        anti_icp_red_flags=["Deeply locked into Datadog Enterprise with 3-year commitments"],
        market_readiness_score=85,
    )
    icp = ICPProfile(
        id="icp_1",
        name="High-Growth Kubernetes Native",
        target_roles=["CTO", "VP Engineering"],
        min_employees=50,
        max_employees=500,
        required_tech_signals=["kubernetes", "aws"],
        buying_triggers=["AWS cost spike"],
        instant_disqualifiers=["No container workloads"],
        vector_doc_id="doc_icp_1",
    )

    await store.index_knowledge(startup, audit, [icp])

    golden_lead = LeadRecord(
        id="lead_golden",
        full_name="Sarah Connor",
        role="VP Engineering",
        company="Skynet",
        domain="skynet.io",
        industry="Technology",
        employee_count=120,
        funding_stage="Series B",
        tech_stack=["kubernetes", "aws"],
        recent_signal="AWS spend jumped 4x",
        bio_snippet="Kubernetes infra leader",
        email="sarah@skynet.io",
    )

    bad_lead = LeadRecord(
        id="lead_bad",
        full_name="Dave Smith",
        role="Junior Admin",
        company="LockedCo",
        domain="locked.com",
        industry="Legacy Retail",
        employee_count=15,
        funding_stage="Seed",
        tech_stack=["datadog"],
        recent_signal="Signed 3yr Datadog contract",
        bio_snippet="Locked in",
        email="dave@locked.com",
    )

    priors, calls = await store.index_and_score_leads([golden_lead, bad_lead])

    assert priors["lead_golden"].prior_score_100 > priors["lead_bad"].prior_score_100
    assert priors["lead_golden"].prior_score_100 >= 70
    assert priors["lead_bad"].prior_score_100 < 50
    assert priors["lead_bad"].anti_icp_similarity_score > priors["lead_golden"].anti_icp_similarity_score


def test_memory_registry_isolation_and_cap():
    """Verify MemoryRegistry isolates runs, evicts oldest beyond max_runs, and respects TTL."""
    registry = MemoryRegistry(max_runs=2, ttl_seconds=1)

    store1 = registry.get_or_create("run_1")
    store2 = registry.get_or_create("run_2")

    assert registry.get("run_1") is store1
    assert registry.get("run_2") is store2

    # Adding a 3rd run should evict run_1 (since run_2 was touched after run_1)
    # Touch run_2 first
    registry.get("run_2")
    store3 = registry.get_or_create("run_3")

    assert registry.get("run_1") is None  # evicted
    assert registry.get("run_2") is store2
    assert registry.get("run_3") is store3

    # Test TTL expiration
    time.sleep(1.1)
    assert registry.get("run_2") is None
    assert registry.get("run_3") is None
