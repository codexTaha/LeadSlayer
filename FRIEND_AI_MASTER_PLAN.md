# LeadSlayer AI — Autonomous AI Engine Master Plan (Friend's Workspace)

> **TO THE AI CODING ASSISTANT (ANTIGRAVITY) READING THIS:**
> You currently have **zero prior context** about this project. Read this entire specification carefully from top to bottom before writing any code. This document is the **complete, authoritative engineering blueprint** for the **AI & Vector Memory Engine (Stages 2 & 3)** of **LeadSlayer AI**.
>
> **How this project is split across 2 laptops:**
> * **Lead Developer (Main Repo Owner):** Builds Stage 1 (Data Contracts, `schemas.py`, `data/leads_50.json`, FastAPI shell), Stage 4 (SSE Streaming Bus, Pacing, RunManager, Exports), Stage 5–6 (Next.js Command Center UI), and Stage 7 (Final Integration).
> * **YOU (This Laptop — Pure AI Brain):** Build **ONLY Stage 2 (`backend/app/memory/`)** and **Stage 3 (`backend/app/agents/`)** + their unit tests and a standalone CLI verification script. You do **NOT** build FastAPI routers, SSE servers, or any Next.js frontend code.

---

## 1. Project Context & Vision (Why This Exists)

**LeadSlayer AI: The Autonomous GTM (Go-To-Market) Engine** solves a real problem for technical founders: standard AI sales tools blindly scrape lead lists and spam everyone, destroying domain reputation.

LeadSlayer AI flips this completely:
1. It ingests a startup's product and founder assumptions.
2. **Market Auditor** audits market reality and locks in **Anti-ICP Red Flags**.
3. **ICP Engine** generates 3 Ideal Customer Profiles (ICPs) and embeds product truth + ICPs + Anti-ICPs into vector memory.
4. **Hunter Swarm** ingests/validates 50 raw B2B leads and scores them mathematically via Dual-Polarity Hybrid Retrieval.
5. **The Slayer Agent (Core Differentiator)** acts as an **adversarial filter**—aggressively hunting for reasons to **DISQUALIFY (KILL)** ~84% of leads so only the top ~8 survive, scaled by user-selected aggression (`LENIENT`, `NORMAL`, `RUTHLESS`).
6. **The Sniper Agent** retrieves exact matching product capabilities from vector memory and drafts hyper-personalized, evidence-backed emails *only* for survivors (plus on-demand when a user clicks **Resurrect** on a killed lead).

---

## 2. Non-Negotiable Engineering Rules & Constraints

1. **Strict 3-Model Google Ecosystem Routing (NEVER violate):**
   * `gemini-4-hydrogen` — Heavy reasoning ONLY (**Step 1: Market Auditor**, **Step 2: ICP Engine**, **Step 5: Sniper Email Drafting & Resurrect**).
   * `gemini-3.5-flash-lite` — High-speed, high-quota volume triage (**Step 3: Sparse CSV Enrichment** if needed, **Step 4: 50-Lead Slayer Agent**).
   * `gemini-embedding-2` — Vector embeddings ONLY (Product chunks, ICPs, Anti-ICPs, 50 Leads, Sniper grounding queries).
   * **FORBIDDEN:** Do NOT use OpenAI, Anthropic, local HuggingFace `sentence-transformers`, PyTorch, Pinecone, ChromaDB, Qdrant, or Redis.
2. **Strict File Ownership Boundary:**
   * **ONLY create/edit files in:**
     * `backend/app/memory/`
     * `backend/app/agents/`
     * `backend/app/scripts/verify_ai_standalone.py`
     * `backend/tests/test_stage2_memory.py`
     * `backend/tests/test_stage3_agents.py`
   * **DO NOT modify** `backend/app/models/schemas.py`, `backend/app/config.py`, `backend/app/services/`, `data/`, or anything outside your scope. The Lead Developer will drop your folders directly into the master repo; modifying shared files will cause merge conflicts.
3. **Strict Integrity Policy (ZERO Fake / Dummy AI Outputs):**
   * Never write hardcoded/fake LLM verdicts, canned email drafts, or random/hash fallback vectors in `memory/` or `agents/`.
   * If a vector is missing from the 6-hour cache or an LLM call fails after gentle retries (`429`, `RESOURCE_EXHAUSTED`, `503`, overload, timeout), **raise `GeminiAPIUnavailableError`** with a clear user-facing message so the UI surfaces the real error honestly.
4. **Strict SDK Inspection Before Coding:**
   * Before writing code that imports `google.adk` or `google.genai`, inspect the installed package versions and exact class/config signatures inside the active Python environment (`python -c "import google.adk, google.genai; ..."`). Never guess SDK parameter names.

---

## 3. Shared Contracts Reference (Provided by Lead Developer in `backend/app/models/schemas.py`)

Your code MUST consume and emit these exact Pydantic v2 types from `app.models.schemas` (already present in the starter repo you received):

### 3.1 Enums
* `SlayingLevel`: `"LENIENT" | "NORMAL" | "RUTHLESS"`
* `ExecutionMode`: `"LIVE" | "SAFE_REPLAY"`
* `PipelinePhase`: `"IDLE" | "AUDITING" | "ICP_GENERATION" | "HUNTING" | "SLAYING" | "SNIPING" | "READY" | "DISPATCHED" | "ERROR"`
* `RejectionCategory`:
  * `"COMPETITOR_LOCK_IN"`
  * `"TOO_SMALL"`
  * `"LAYOFFS_FREEZE"`
  * `"WRONG_PERSONA"`
  * `"NO_STACK_FIT"`
  * `"BUILT_IN_HOUSE"`
  * `"NO_URGENCY_SIGNAL"`
* `ModelId`: `"gemini-4-hydrogen" | "gemini-3.5-flash-lite" | "gemini-embedding-2"`

### 3.2 Core Pydantic Models (Exact Fields)
1. **`StartupInput`**: `product_name: str`, `product_url: str | None`, `description: str`, `founder_assumptions: str`, `slaying_level: SlayingLevel = "RUTHLESS"`, `execution_mode: ExecutionMode = "LIVE"`, `leads: list[LeadRecord] | None`
2. **`MarketAuditResult`**:
   * `market_reality_summary: str`, `founder_blind_spots: list[str]`, `sharpened_value_prop: str`, `anti_icp_red_flags: list[str]`, `market_readiness_score: int` (`0–100`)
   * `url_scraped_context_used: bool = False`, `search_grounding_used: bool = False`
   * `assumption_gaps: list[AssumptionGap]` (`{ founder_belief, market_reality, severity, strategic_fix }`)
   * `competitor_landscape: list[CompetitorInsight]` (`{ name, positioning_weakness, switching_trigger }`)
   * `buying_objections: list[BuyingObjection]` (`{ objection, buyer_role, counter_angle }`)
   * `readiness_breakdown: ReadinessBreakdown | None` (`{ pain_urgency, icp_clarity, differentiation, timing_fit }`)
3. **`ICPProfile`**: `id: str` (`"icp_1"`..`"icp_3"`), `name: str`, `target_roles: list[str]`, `min_employees: int`, `max_employees: int`, `required_tech_signals: list[str]`, `buying_triggers: list[str]`, `instant_disqualifiers: list[str]`, `vector_doc_id: str`
4. **`HunterReport`**: `hunt_queries: list[HuntQuery]` (`{ source, query_string, signal_target }`), `enriched_sparse_leads: int`, `url_fetches_succeeded: int`, `total_leads_ready: int`
5. **`LeadRecord`**: `id: str`, `full_name: str`, `role: str`, `company: str`, `domain: str`, `industry: str`, `employee_count: int`, `funding_stage: str`, `tech_stack: list[str]`, `recent_signal: str`, `bio_snippet: str`, `email: str`
5. **`SlayerVerdict`**:
   * `lead_id: str`
   * `survived: bool`
   * `resurrected_by_user: bool = False`
   * `rejection_category: RejectionCategory | None` (required if `survived=False`, `None` if `survived=True`)
   * `headline_tag: str` (max 5 words, e.g. `"KILLED: Datadog Lock-In"` or `"SURVIVED: 3.2x AWS Spike"`)
   * `reasoning: str` (1–2 sentences citing exact lead facts)
   * `matched_icp_id: str | None`
   * `icp_similarity_score: float` (`0.0–1.0`)
   * `anti_icp_similarity_score: float` (`0.0–1.0`)
   * `structural_match_score: float` (`0.0–1.0`)
   * `qualification_score: int` (`0–100`)
   * `confidence: float` (`0.0–1.0`)
   * `slaying_level_applied: SlayingLevel`
   * `latency_ms: int`
   * `model_used: ModelId = "gemini-3.5-flash-lite"`
6. **`EmailDraft`**:
   * `lead_id: str`, `recipient_name: str`, `recipient_email: str`, `company: str`
   * `subject: str`, `body: str`
   * `cited_survival_signal: str`
   * `email_evidence_phrase: str` *(CRITICAL: exact verbatim substring inside `body`!)*
   * `matched_product_chunk: str`
   * `personalization_score: int` (`0–100`)
   * `approved: bool = True`
   * `status: Literal["DRAFTED", "SENT"] = "DRAFTED"`

### 3.3 The Integration Boundary Contract (`backend/app/agents/interface.py`)
The Lead Developer's `RunManager` will call **ONLY these 2 async functions** from your `agents/` package using the `PipelineCallbacks` protocol. (If `interface.py` is already in your starter repo, keep it exact; if not, create `backend/app/agents/interface.py` with this exact contract):

```python
from typing import Protocol
from pydantic import BaseModel
from app.models.schemas import (
    EmailDraft, HunterReport, ICPProfile, MarketAuditResult,
    ModelId, PipelinePhase, SlayerVerdict
)

class PipelineCallbacks(Protocol):
    async def on_phase(self, phase: PipelinePhase) -> None: ...
    async def on_log(self, message: str) -> None: ...
    async def on_model_call(self, model_id: ModelId) -> None: ...
    async def on_audit(self, audit: MarketAuditResult) -> None: ...
    async def on_icps(self, icps: list[ICPProfile]) -> None: ...
    async def on_hunter_report(self, report: HunterReport) -> None: ...
    async def on_verdict(self, verdict: SlayerVerdict) -> None: ...
    async def on_email(self, draft: EmailDraft) -> None: ...

class PipelineFinalResult(BaseModel):
    run_id: str
    market_audit: MarketAuditResult
    icps: list[ICPProfile]
    hunter_report: HunterReport | None = None
    verdicts: dict[str, SlayerVerdict]
    emails: dict[str, EmailDraft]
```

**Your Two Public Entry Points:**
1. In `backend/app/agents/pipeline.py`:
   `async def run_live_pipeline(run_id: str, startup_input: StartupInput, leads: list[LeadRecord], callbacks: PipelineCallbacks) -> PipelineFinalResult`
2. In `backend/app/agents/sniper_agent.py`:
   `async def resurrect_single_lead(run_id: str, lead: LeadRecord, old_verdict: SlayerVerdict, icp: ICPProfile) -> tuple[SlayerVerdict, EmailDraft]`

---

## 4. Target Folder Structure (What You Will Build)

```text
backend/
├── app/
│   ├── memory/                          # STAGE 2: Vector Memory & Hybrid Context Engine
│   │   ├── __init__.py
│   │   ├── exceptions.py                # GeminiAPIUnavailableError
│   │   ├── cache.py                     # BoundedTTLEmbeddingCache (6h TTL, 1000 max LRU, atomic JSON)
│   │   ├── embedder.py                  # GeminiEmbedder (gemini-embedding-2, 768d, batch=25, retry=1)
│   │   ├── chunker.py                   # Semantic section chunker
│   │   ├── structural_matcher.py        # Tech-stack aliases + company size + role matcher
│   │   ├── vector_store.py              # HybridMemoryStore (NumPy float32, dual-polarity math)
│   │   └── registry.py                  # MemoryRegistry (per-run isolation, max 20 runs, 6h TTL)
│   │
│   ├── agents/                          # STAGE 3: Google ADK 2.0 Pipeline & Slayer/Sniper
│   │   ├── __init__.py
│   │   ├── interface.py                 # PipelineCallbacks & PipelineFinalResult (read-only contract)
│   │   ├── structured_outputs.py        # Think-first LLM Pydantic schemas
│   │   ├── prompts.py                   # Tiered Slaying rubrics + Anti-ICP injection + Sniper prompt
│   │   ├── rate_limiter.py              # GentleAdaptiveExecutor (Semaphore(5), 60ms stagger, cooldown)
│   │   ├── auditor_agent.py             # ADK LlmAgent (gemini-4-hydrogen)
│   │   ├── icp_agent.py                 # ADK LlmAgent (gemini-4-hydrogen) + Stage 2 index build
│   │   ├── hunter_agent.py              # ADK BaseAgent (validate + sparse CSV flash-lite enrichment)
│   │   ├── slayer_agent.py              # ADK BaseAgent (gemini-3.5-flash-lite 50-lead triage)
│   │   ├── sniper_agent.py              # ADK LlmAgent (gemini-4-hydrogen) + resurrect_single_lead
│   │   └── pipeline.py                  # ADK SequentialAgent + Runner + run_live_pipeline()
│   │
│   └── scripts/
│       └── verify_ai_standalone.py      # Standalone CLI runner testing Stages 2+3 without FastAPI/UI
│
└── tests/
    ├── test_stage2_memory.py            # Comprehensive unit tests for Stage 2
    └── test_stage3_agents.py            # Comprehensive unit tests for Stage 3
```

---

## 5. Exact Step-by-Step Build Sequence

Execute these phases **in exact order**. Do not skip ahead or batch Stage 3 before Stage 2 passes all unit tests.

### PHASE A: Environment & SDK Verification (10 Minutes)
1. Activate the backend Python virtual environment inside `backend/`.
2. Verify `data/default_startup.json`, `data/leads_50.json`, and `backend/app/models/schemas.py` exist and load cleanly.
3. Inspect the installed `google-genai` and `google-adk` APIs:
   * Confirm how `genai.Client(api_key=...)` calls `models.embed_content(...)` with `output_dimensionality=768` and `task_type`.
   * Confirm exact `google.adk.agents` (`LlmAgent`, `BaseAgent`, `SequentialAgent`), `google.adk.runners.Runner`, `google.adk.sessions.InMemorySessionService`, and `InvocationContext` signatures in the installed `google-adk` version.
4. Check `.env` has `GEMINI_API_KEY` set (never hardcode API keys in code!).

---

### PHASE B: Build Stage 2 — Vector Memory & Hybrid Context Engine (`backend/app/memory/`)

#### Step B1: `memory/exceptions.py`
* Create `GeminiAPIUnavailableError(Exception)` storing `user_message: str`, `status_code: int | None = None`, `raw_error: str = ""`.
* Default `user_message`:
  `"Gemini API limit reached or service is temporarily overloaded. Please wait a short while and try again."`
* Provide a helper `is_transient_api_error(exc: Exception) -> tuple[bool, int | None]` detecting `429`, `503`, `500`, `RESOURCE_EXHAUSTED`, `overloaded`, or `TimeoutError` / `asyncio.TimeoutError`.

#### Step B2: `memory/cache.py` — `BoundedTTLEmbeddingCache`
Protect system RAM & disk while accelerating repeat runs:
* **Cache Key:** `hashlib.sha256(f"{model_id}:{dim}:{task_type}:{normalized_text}".encode("utf-8")).hexdigest()`
* **Disk File:** `data/.emb_cache.json` (configurable path for tests):
  ```json
  {
    "version": 1,
    "dim": 768,
    "entries": {
      "<sha256>": { "created_at": 1732640000.0, "last_used": 1732640000.0, "vector": [0.012, ...] }
    }
  }
  ```
* **Hard Resource Guards:**
  1. `ttl_seconds: int = 21600` (**6 hours max**). On load, on `get_many`, and before flush, purge any item where `time.time() - created_at > ttl_seconds`.
  2. `max_entries: int = 1000` (~3.1 MB RAM max). Use `collections.OrderedDict`; on `put_many`, evict expired entries first, then oldest `last_used` entries via `popitem(last=False)` until `len <= 1000`.
  3. `max_text_bytes: int = 16384`. Reject inputs >16 KB cleanly before hashing.
  4. **Concurrency & Atomic Writes:** Protect mutations with `asyncio.Lock()`. Flush to disk **only once per `put_many(..., flush=True)`** when dirty—never inside per-item loops. Write to `<path>.tmp` and swap via `os.replace(tmp, path)`.

#### Step B3: `memory/embedder.py` — `GeminiEmbedder`
* **Config:** `model = "gemini-embedding-2"`, `output_dimensionality = 768`, `batch_size = 25`, `max_retries = 1`.
* **Task Types:** Use `"RETRIEVAL_DOCUMENT"` when indexing product chunks, ICPs, and Anti-ICPs; use `"SEMANTIC_SIMILARITY"` (or `"RETRIEVAL_QUERY"`) for leads and Sniper grounding queries (matching installed `google-genai` enum).
* **Method:** `async def embed_texts(self, texts: list[str], task_type: str) -> tuple[np.ndarray, int]` (returns `(N, 768)` L2-normalized `float32` matrix + number of live API batch calls made for telemetry).
* **Execution Flow:**
  1. If `texts` is empty, return `(np.zeros((0, 768), dtype=np.float32), 0)`.
  2. Normalize whitespace and compute SHA-256 keys; call `cache.get_many(keys)`.
  3. If 0 misses → return cached L2-normalized matrix + `0` API calls.
  4. Split missed indices into batches of `25`.
  5. For each batch: call Gemini `embed_content` via `asyncio.to_thread(...)` (if SDK method is sync) or async SDK client.
     * On transient error (`429`/`503`/timeout): sleep `1.5s`, retry **once** (`max_retries=1`).
     * If retry fails OR non-transient error: **raise `GeminiAPIUnavailableError`** immediately! **NEVER return zero/random/fake hash vectors.**
  6. L2-normalize every vector: `v / np.maximum(np.linalg.norm(v), 1e-12)`.
  7. Store new vectors in cache via `put_many(..., flush=True)` and return full ordered matrix.

#### Step B4: `memory/chunker.py`
* Define `KnowledgeChunk(BaseModel)`: `chunk_id: str`, `section: Literal["CORE_PITCH", "PAIN_SOLVED", "TECH_CAPABILITY", "PROOF_POINT"]`, `text: str`.
* Implement `chunk_startup_and_audit(startup: StartupInput, audit: MarketAuditResult) -> tuple[list[KnowledgeChunk], list[str]]`:
  * Builds 4–8 crisp, self-contained product chunks (`<= 120` words each) covering `sharpened_value_prop`, `market_reality_summary`, technical capabilities split cleanly from `startup.description`, and `founder_blind_spots` counters.
  * Returns `(product_chunks, audit.anti_icp_red_flags)`.

#### Step B5: `memory/structural_matcher.py`
* Implement `TECH_ALIASES` dictionary normalizing variants before comparison:
  `{"k8s": "kubernetes", "eks": "kubernetes", "gke": "kubernetes", "aks": "kubernetes", "aws ec2": "aws", "ec2": "aws", "gcp": "google cloud", "datadog apm": "datadog", "tf": "terraform"}`.
* Implement `score_structural_fit(lead: LeadRecord, icp: ICPProfile) -> float` returning `0.0–1.0`:
  * `stack_overlap` (`0.55` weight): `len(lead_norm & icp_norm) / max(1, len(icp_norm))` (clamped `0..1`)
  * `size_fit` (`0.30` weight): `1.0` if `icp.min_employees <= lead.employee_count <= icp.max_employees`; linearly decays to `0.0` outside `[0.5 * min, 3.0 * max]`
  * `role_fit` (`0.15` weight): token/keyword match between `lead.role.lower()` and `icp.target_roles` (e.g. `cto`, `vp`, `engineering`, `infra`, `platform`, `devops`).

#### Step B6: `memory/vector_store.py` — `HybridMemoryStore`
* Define exact serialization templates so embeddings align semantically:
  * `serialize_icp(icp)`: `f"Target ICP: {icp.name}. Roles: {', '.join(icp.target_roles)}. Company size: {icp.min_employees}-{icp.max_employees}. Required stack: {', '.join(icp.required_tech_signals)}. Buying triggers: {'; '.join(icp.buying_triggers)}."`
  * `serialize_lead(lead)`: `f"Role: {lead.role} at {lead.company} ({lead.industry}, {lead.employee_count} employees, {lead.funding_stage}). Stack: {', '.join(lead.tech_stack)}. Recent signal: {lead.recent_signal}. Bio: {lead.bio_snippet}"`
* Define typed outputs:
  * `HybridMatchContext(BaseModel)`: `lead_id`, `best_icp: ICPProfile`, `icp_similarity_score: float`, `anti_icp_similarity_score: float`, `matched_anti_icp_rule: str`, `structural_match_score: float`, `prior_score_100: int`.
  * `SniperGrounding(BaseModel)`: `lead_id: str`, `top_product_chunks: list[KnowledgeChunk]`, `matched_icp: ICPProfile`.
* Implement:
  1. `async def index_knowledge(startup, audit, icps) -> int`: embeds product chunks, 3 ICPs, and Anti-ICPs (`RETRIEVAL_DOCUMENT`), stores normalized `np.float32` matrices. Returns API batch calls count.
  2. `async def index_and_score_leads(leads: list[LeadRecord]) -> tuple[dict[str, HybridMatchContext], int]`: batch-embeds all 50 leads (`SEMANTIC_SIMILARITY`, 2 calls of 25), then computes via NumPy matrix dot products:
     * `icp_sim = clip(max(leads @ icps.T, axis=1), 0.0, 1.0)` & `best_icp`
     * `anti_icp_sim = clip(max(leads @ anti_icps.T, axis=1), 0.0, 1.0)` & `matched_anti_icp_rule`
     * `struct_score = score_structural_fit(lead, best_icp)`
     * `raw_hybrid = 0.60 * icp_sim + 0.25 * struct_score - 0.15 * anti_icp_sim`
     * `prior_score_100 = int(round(np.clip(raw_hybrid, 0.0, 1.0) * 100))`
  3. `async def get_sniper_grounding(lead, survival_reason, matched_icp, top_k=2) -> tuple[SniperGrounding, int]`: embeds lead + survival query, computes `product_chunks @ query_vec`, returns top-2 chunks + `matched_icp`.

#### Step B7: `memory/registry.py` — `MemoryRegistry`
* Singleton/injectable `OrderedDict[str, tuple[float, HybridMemoryStore]]` keyed by `run_id`.
* Hard caps: `max_runs = 20`, `ttl_seconds = 21600` (6 hours). Purges expired runs on `get_or_create(run_id)` and evicts oldest when `> 20` runs so FastAPI never leaks RAM. (Important: `resurrect_single_lead` looks up the existing `HybridMemoryStore` from `MemoryRegistry` using `run_id`!)

#### Step B8: Write & Run `backend/tests/test_stage2_memory.py`
Verify with mocked Gemini embedder (no network needed in unit tests):
1. Cache respects 6-hour TTL (`ttl_seconds=1` test proves expired entry triggers re-embed).
2. Cache enforces `max_entries` LRU eviction cleanly.
3. Atomic flush creates valid JSON without leaving `.tmp` files behind.
4. When cache misses and mocked Gemini throws `429`/overload twice, `GeminiAPIUnavailableError` is raised (no fake vectors).
5. Dual-polarity math scores a golden K8s Series B CTO strictly higher than a Datadog-locked or layoff lead.
6. `MemoryRegistry` isolates `run_id`s and enforces `max_runs=20` & 6h TTL.

**Gate:** Run `pytest backend/tests/test_stage2_memory.py` → MUST pass 100% before starting Phase C!

---

### PHASE C: Build Stage 3 — Google ADK 2.0 Pipeline & Slayer Engine (`backend/app/agents/`)

#### Step C1: `agents/structured_outputs.py`
Create LLM-facing Pydantic schemas used as ADK `output_schema` / Gemini `response_schema`:
1. **`_ICPBatchOutput`**: `icps: list[ICPProfile]` (validated length == 3).
2. **`_EnrichedLeadPatch`**: `lead_id: str`, `inferred_tech_stack: list[str]`, `inferred_signal: str` (only used if a messy custom CSV is missing fields).
3. **`_SlayerLLMResponse`** *(CRITICAL FIELD ORDER — forces adversarial thinking BEFORE verdict!)*:
   1. `disqualifier_signals_found: list[str]`
   2. `tier_triggered: Literal["NONE", "TIER_1_HARD", "TIER_2_ICP_FIT", "TIER_3_FRICTION"]`
   3. `rejection_category: RejectionCategory | None`
   4. `reasoning: str` (1–2 sentences citing specific facts)
   5. `survived: bool`
   6. `headline_tag: str` (max 5 words, e.g. `"KILLED: Datadog Lock-In"` or `"SURVIVED: 3.2x AWS Spike"`)
   7. `confidence: float` (`0.0–1.0`)
4. **`_SniperLLMResponse`**:
   * `cited_survival_signal: str`
   * `subject: str` (max 9 words, technical peer tone, zero spam words like "revolutionize" or "synergy")
   * `body: str` (`75–130` words, concrete & concise)
   * `email_evidence_phrase: str` (exact verbatim substring from `body`)
   * `personalization_score: int` (`0–100`)

#### Step C2: `agents/prompts.py`
Build crisp, deterministic prompt builders:
1. **`AUDITOR_SYSTEM_PROMPT`**: Evaluates startup product + founder's naive assumptions against real B2B buying dynamics; outputs `MarketAuditResult` including **4–5 concrete `anti_icp_red_flags`** that directly feed the Slayer.
2. **`ICP_ENGINE_SYSTEM_PROMPT`**: Generates exactly 3 distinct, sharp `ICPProfile`s with realistic employee ranges, required tech signals, buying triggers, and instant disqualifiers.
3. **`build_slayer_system_prompt(slaying_level: SlayingLevel, anti_icp_red_flags: list[str])`**:
   * Embeds the **Tiered Disqualification Rubric**:
     * **TIER 1 (Hard Blockers — KILL in ALL modes: `LENIENT`, `NORMAL`, `RUTHLESS`):**
       - `COMPETITOR_LOCK_IN`: Signed multi-year contract or deep lock-in with direct competitor.
       - `WRONG_PERSONA`: Non-buyer role (HR, Brand Designer, Sales Rep, Intern, no technical/budget authority).
       - `LAYOFFS_FREEZE`: Active layoffs, hiring freeze, CFO spend freeze, or acquisition freeze.
     * **TIER 2 (ICP & Stack Fit — KILL in `NORMAL` & `RUTHLESS`; allow in `LENIENT` unless totally unrelated):**
       - `TOO_SMALL`: Headcount far below ICP minimum or tiny pre-scale prototype.
       - `NO_STACK_FIT` / `BUILT_IN_HOUSE`: Incompatible infra (pure on-prem mainframe) or large dedicated internal platform/FinOps team.
     * **TIER 3 (Urgency & Friction — KILL ONLY in `RUTHLESS`):**
       - `NO_URGENCY_SIGNAL`: Right persona & stack, *but* no urgent trigger, recent leadership change creating transition friction, or weak Stage 2 prior (`prior_score_100 < 68`).
   * Injects the live `anti_icp_red_flags` list from Step 1!
   * In `RUTHLESS` mode, explicitly commands: *"Assume every lead is a waste of domain reputation unless undeniable urgent pain AND ICP fit exist."*
4. **`SNIPER_SYSTEM_PROMPT`**: Instructs `gemini-4-hydrogen` to write like a sharp technical founder emailing a peer—weaving in the lead's `recent_signal` + Stage 2's top-2 retrieved product chunks, and copying `email_evidence_phrase` verbatim from `body`.

#### Step C3: `agents/rate_limiter.py` — `GentleAdaptiveExecutor`
Built for maximum reliability against Gemini API rate limits:
* `concurrency: int = 5` (`asyncio.Semaphore(5)`)
* `launch_stagger_s: float = 0.06` (`60ms` gentle stagger on task start)
* `max_retries: int = 2` (backoff `1.5s`, `3.5s` + `0–300ms` random jitter)
* **Shared Cooldown Gate (`asyncio.Event`):** If *any* worker hits `429` or `503`:
  * Clears the event so sibling workers pause instead of piling onto an overloaded endpoint.
  * Sleeps backoff + jitter, then sets the event again.
  * If all retries fail → raises `GeminiAPIUnavailableError`!
* **Method:** `async def run_stream(items: list[T], worker_fn: Callable[[T], Awaitable[R]]) -> AsyncIterator[tuple[T, R]]` yielding `(item, result)` via `asyncio.as_completed` as each finishes.

#### Step C4: Implement the 5 ADK Agents (`auditor`, `icp`, `hunter`, `slayer`, `sniper`)
1. **`auditor_agent.py` (Market Research + Gap Analysis + URL Context):**
   * First, if `startup_input.product_url` is set, call the pre-built helper `await fetch_site_context(startup_input.product_url, timeout_s=3.0)` from `app.services.url_fetcher`! Inject any extracted landing-page text into the prompt and set `url_scraped_context_used=True` if non-empty (cleanly ignore if `None`).
   * Optionally enable **Gemini Google Search Grounding** (`google_search` tool in `google-adk` / `google-genai`, verifying SDK syntax first) on a research pre-pass or directly if supported alongside structured output; if search grounding fails or is unavailable offline, fall back cleanly to pure `gemini-4-hydrogen` reasoning (`search_grounding_used=False`) without ever crashing!
   * ADK `LlmAgent(name="market_auditor", model="gemini-4-hydrogen", output_schema=MarketAuditResult, output_key="market_audit")`.
   * Must populate `assumption_gaps` (2–3 side-by-side Founder Belief vs. Market Reality gaps), `competitor_landscape` (2–4 competitors + switching triggers), `buying_objections` (2–3 objections + counter-angles), `readiness_breakdown`, and **4–5 `anti_icp_red_flags`**.
   * Executes via ADK `Runner` + `InMemorySessionService`, emits `callbacks.on_phase("AUDITING")`, `callbacks.on_model_call("gemini-4-hydrogen")`, `callbacks.on_audit(audit)`.
2. **`icp_agent.py`:**
   * ADK `LlmAgent(name="icp_engine", model="gemini-4-hydrogen", output_schema=_ICPBatchOutput, output_key="icps")`.
   * Emits `callbacks.on_phase("ICP_GENERATION")`, `callbacks.on_model_call("gemini-4-hydrogen")`, `callbacks.on_icps(icps)`.
   * Calls `memory_store.index_knowledge(startup_input, audit, icps)` → emits `callbacks.on_model_call("gemini-embedding-2")` for embedding batches.
3. **`hunter_agent.py` (Hunt Query Generation + Smart Enrichment):**
   * ADK `BaseAgent` (`HunterSwarmAgent`): emits `callbacks.on_phase("HUNTING")`.
   * **Always generates 3–4 visible `HuntQuery` objects** from the 3 ICPs (either deterministically + 1 lightweight `gemini-3.5-flash-lite` query-synthesis call so judges see the exact Boolean hunt queries & signal sources).
   * Checks `leads` from `session.state`. If `> 20%` of leads lack `tech_stack` or `recent_signal` (sparse bare-bones custom CSV), uses `fetch_site_context(f"https://{lead.domain}", timeout_s=2.0)` (via `GentleAdaptiveExecutor(concurrency=5)`) + `gemini-3.5-flash-lite` in batches of 10 to enrich missing signals! On clean 50-lead preset/CSV data, skips lead-by-lead enrichment (`enriched_sparse_leads=0`, zero wasted latency!).
   * Emits `await callbacks.on_hunter_report(HunterReport(...))`.
   * Calls `memory_store.index_and_score_leads(leads)` → saves `hybrid_priors` (`dict[str, HybridMatchContext]`) to `session.state`.
4. **`slayer_agent.py`:**
   * ADK `BaseAgent` (`SlayerSwarmAgent`): emits `callbacks.on_phase("SLAYING")`.
   * Runs all 50 leads through `GentleAdaptiveExecutor` (`Semaphore(5)`, `60ms` stagger) calling `gemini-3.5-flash-lite` with `_SlayerLLMResponse` structured output.
   * For each finished lead:
     * Measures `latency_ms`.
     * Fuses Stage 2 `prior_score_100` with Slayer confidence:
       * If `survived`: `qualification_score = max(65, min(99, round(0.40 * prior + 0.60 * (conf * 100))))`
       * If killed: `qualification_score = max(4, min(62, round(0.40 * prior + 0.60 * ((1 - conf) * 100))))`
     * Normalizes `headline_tag` (max 5 words; enforces `"KILLED: ..."` or `"SURVIVED: ..."` prefix).
     * Builds `SlayerVerdict`, saves to `verdicts_map`, calls `await callbacks.on_model_call("gemini-3.5-flash-lite")` and `await callbacks.on_verdict(verdict)` **immediately**.
5. **`sniper_agent.py`:**
   * Runs `callbacks.on_phase("SNIPING")`.
   * Filters `survived == True` leads and runs with `GentleAdaptiveExecutor(concurrency=4)` on `gemini-4-hydrogen`:
     1. Calls `memory_store.get_sniper_grounding(lead, verdict.reasoning, matched_icp, top_k=2)`.
     2. Invokes `gemini-4-hydrogen` with `_SniperLLMResponse`.
     3. **Deterministic Substring Verifier:** Ensures `email_evidence_phrase` exists inside `body` (case-insensitive check → if slightly paraphrased, falls back cleanly to the sentence in `body` overlapping most tokens with `cited_survival_signal` so the UI highlight *always* resolves cleanly).
     4. Emits `callbacks.on_email(draft)`.
   * **Also implements `resurrect_single_lead(run_id, lead, old_verdict, icp)`:**
     * Looks up `memory_store = memory_registry.get(run_id)` (or rebuilds grounding cleanly if needed), runs Step 1–3 above on `gemini-4-hydrogen`, returns updated `SlayerVerdict(survived=True, resurrected_by_user=True, ...)` + `EmailDraft`.

#### Step C5: `agents/pipeline.py`
* Wires all 5 ADK agents into an ADK `SequentialAgent(name="leadslayer_pipeline", sub_agents=[...])` executed via `Runner` + `InMemorySessionService`.
* Exposes `run_live_pipeline(run_id, startup_input, leads, callbacks) -> PipelineFinalResult`.
* Ensures any `GeminiAPIUnavailableError` propagates cleanly upward without swallowing or returning fake results.

#### Step C6: Write & Run `backend/tests/test_stage3_agents.py`
Verify with mocked Gemini clients:
1. `_SlayerLLMResponse.model_fields` preserves think-first order (`disqualifier_signals_found` before `survived`).
2. `RUTHLESS` kills Tier 1 + Tier 2 + Tier 3 borderline leads, while `LENIENT` passes Tier 3.
3. `GentleAdaptiveExecutor` triggers shared cooldown on `429` and raises `GeminiAPIUnavailableError` after 2 failed retries.
4. Sniper substring verifier guarantees `email_evidence_phrase in draft.body` even if the LLM slightly alters casing/punctuation.
5. `resurrect_single_lead` flips `survived=True, resurrected_by_user=True` and returns a grounded `EmailDraft`.

**Gate:** Run `pytest backend/tests/test_stage3_agents.py` → MUST pass 100%!

---

### PHASE D: Standalone End-to-End Live Verification (`verify_ai_standalone.py`)

Write `backend/app/scripts/verify_ai_standalone.py` that:
1. Loads `data/default_startup.json` and `data/leads_50.json` directly (no FastAPI server needed).
2. Runs `run_live_pipeline(...)` with a simple `ConsoleCallbacks` printer logging every phase, kill/survive verdict, and drafted email.
3. Tests `RUTHLESS` mode and checks:
   * Total runtime `< 25 seconds`.
   * Kill rate is **`76%–90%`** (target ~40–44 killed, ~6–10 survived out of 50).
   * Every surviving `EmailDraft` has `email_evidence_phrase in body` and cites real lead signals.
4. Tests `resurrect_single_lead(...)` on 1 killed lead and prints the drafted email.
5. Tests `LENIENT` mode on the same 50 leads and confirms strictly more leads survive than in `RUTHLESS`.
6. *(Calibration Rule)* If `RUTHLESS` kills fewer than 38 or more than 45 on the curated `leads_50.json`, refine the prompt wording in `agents/prompts.py` (do NOT edit `leads_50.json` or `schemas.py`).

---

## 6. Final Handoff Checklist (What You Send Back to Lead Developer)

Before zipping/pushing your work for integration into the main app, confirm every box:
- [ ] `backend/app/models/schemas.py` and `data/*` are **untouched**.
- [ ] `pytest backend/tests/test_stage2_memory.py backend/tests/test_stage3_agents.py` passes 100%.
- [ ] `python -m app.scripts.verify_ai_standalone` runs cleanly end-to-end on real Gemini (`gemini-4-hydrogen`, `gemini-3.5-flash-lite`, `gemini-embedding-2`) and hits ~76–90% kill rate in `RUTHLESS` mode.
- [ ] **Only** send/commit:
  1. `backend/app/memory/`
  2. `backend/app/agents/`
  3. `backend/app/scripts/verify_ai_standalone.py`
  4. `backend/tests/test_stage2_memory.py`
  5. `backend/tests/test_stage3_agents.py`
