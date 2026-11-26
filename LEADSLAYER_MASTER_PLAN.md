# LeadSlayer AI — Master Engineering Blueprint & Stage-by-Stage Plan

> **STATUS: ALL 7 STAGES FINALIZED — READY FOR STEP-BY-STEP IMPLEMENTATION**
>
> **Mission:** Build **LeadSlayer AI: The Autonomous GTM Engine** — an adversarial multi-agent system built on **Google ADK 2.0** and **Gemini (`gemini-4-hydrogen`, `gemini-3.5-flash-lite`, `gemini-embedding-2`)** that aggressively disqualifies ~84–90% of noisy leads and crafts evidence-backed outreach only for high-conviction survivors.
>
> **Core Engineering Goal:** Production-grade architecture, deterministic 3-minute live stage demo reliability, and visceral real-time UI feedback within a **16-hour active coding budget**.

---

## Locked Baseline Decisions

| Decision Area | Selected Choice | Summary |
| :--- | :--- | :--- |
| **1. Repo Structure** | **Monorepo** (`1A`) | Single repo: `/frontend`, `/backend`, `/data`, `/contracts` |
| **2. Data Contracts** | **Pydantic v2 → TypeScript** (`2A`) | Backend Pydantic schemas act as single source of truth, mirrored 1:1 in TS |
| **3. Lead Ingestion** | **Dual-Mode CSV + 1-Click Sample** (`3A`) | Real CSV drag-and-drop upload + 1-click "Load 50-Lead Swarm" stage button |
| **4. 50-Lead Dataset** | **Curated Adversarial Dataset** (`4A`) | 50 richly engineered B2B leads with realistic traps & borderline cases evaluated live by AI |
| **5. Stage Safety** | **Live AI + Authentic Cache Replay** (`5A`) | 100% live Gemini calls by default; hidden `?mode=replay` replays **real cached output captured from an actual Gemini run** (never fake/handwritten dummy verdicts) |
| **6. Streaming** | **Typed Server-Sent Events (SSE)** (`6A`) | FastAPI `StreamingResponse` pushing typed JSON event envelopes to React |
| **7. Showcase Domain** | **B2B DevTools / Cloud Cost Guard** (`7A`) | Default product: **KubeGuard AI** (selling to CTOs & VPs of Engineering) |
| **8. Product Energy** | **Dynamic Slaying Levels** *(Added)* | User-selectable `LENIENT` ("Scout"), `NORMAL` ("Tactical"), `RUTHLESS` ("Bloodbath") |
| **9. 10x Upgrades** | **Selected Enhancements** (`#1, #3, #4, #5, #6, #9, #10`) | Evidence-to-Email tracing, Anti-ICP Rules Lock-In, Resurrect Lead override, Slaying Aggression Score (`0–100`), Slayer Autopsy filters, ~90ms Bloodbath SSE pacing + Instant Reset, Survivors CSV & Kill Audit JSON export |

---

## Master Chronological Roadmap (All 7 Stages)

At every stage below, we verify **Architecture**, **Tech & Stack**, **Advanced Techniques**, and **Verification Criteria** before writing code.

- **Stage 1: System Contracts, Event Schema, Slaying Levels & Adversarial Dataset** *(Hours 0–2)* — **[FINALIZED BELOW]**
- **Stage 2: Vector Memory & Hybrid Context Engine (`gemini-embedding-2`)** *(Hours 2–4)* — **[FINALIZED BELOW]**
- **Stage 3: Google ADK 2.0 Multi-Agent Orchestration & Slayer Engine** *(Hours 4–8)* — **[FINALIZED BELOW]**
- **Stage 4: Real-Time SSE Streaming Bus & Agent Telemetry Layer** *(Hours 8–10)* — **[FINALIZED BELOW]**
- **Stage 5: "Command Center" Frontend Foundation & State Machine** *(Hours 10–12)* — **[FINALIZED BELOW]**
- **Stage 6: Kinetic "Bloodbath" UI & Sniper Command Deck (Framer Motion)** *(Hours 12–14.5)* — **[FINALIZED BELOW]**
- **Stage 7: End-to-End Integration, Chaos Hardening & 3-Minute Choreography** *(Hours 14.5–16)* — **[FINALIZED BELOW]**

---

# STAGE 1: FINALIZED IMPLEMENTATION SPECIFICATION
*(Follow step-by-step during implementation — zero guesswork required)*

## 1.1 Exact Monorepo Folder & File Layout

Create the following directory structure inside `/home/taha/Arc_Project/Agent`:

```text
Agent/
├── LEADSLAYER_MASTER_PLAN.md          # This master plan
├── .env.example                       # Template for GEMINI_API_KEY, DEMO_MODE, etc.
├── .gitignore                         # Ignore venv, node_modules, .next, .env
│
├── contracts/                         # Shared schema documentation & validator
│   └── schema_spec.json               # Exported JSON Schema from Pydantic (auto-generated)
│
├── data/                              # Deterministic stage & test datasets
│   ├── default_startup.json           # Default "KubeGuard AI" startup pitch + assumptions
│   ├── leads_50.csv                   # 50-row CSV (works via drag-and-drop upload too)
│   ├── leads_50.json                  # Exact JSON mirror of leads_50.csv for instant load
│   └── replay_snapshot.json           # Placeholder until Stage 7 records a real Gemini run
│
├── backend/                           # Python 3.11+ / FastAPI / Google ADK 2.0
│   ├── pyproject.toml                 # Dependencies & tooling config
│   ├── requirements.txt               # Pinned pip requirements for fast install
│   └── app/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app, CORS, health, router mounting
│       ├── config.py                  # Pydantic Settings (env vars, model names, concurrency)
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py             # ALL Pydantic v2 contracts (Single Source of Truth)
│       ├── services/
│       │   ├── __init__.py
│       │   └── lead_loader.py         # CSV/JSON parser, normalization, validation
│       └── scripts/
│           └── export_schema.py       # Exports Pydantic schemas to /contracts/schema_spec.json
│
└── frontend/                          # Next.js 15 (App Router) / Tailwind / Framer Motion
    ├── package.json
    ├── tsconfig.json
    ├── next.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── types/
        │   └── contracts.ts           # Strict 1:1 TypeScript mirror of backend/app/models/schemas.py
        ├── lib/
        │   └── constants.ts           # Slaying level labels, colors, phase metadata
        └── app/
            ├── layout.tsx
            └── page.tsx               # Stage 1 health-check shell
```

---

## 1.2 Tech Stack & Exact Dependencies (Stage 1 Baseline)

### Backend (`backend/requirements.txt`)
* `fastapi>=0.115.0`
* `uvicorn[standard]>=0.32.0`
* `pydantic>=2.9.0`
* `pydantic-settings>=2.6.0`
* `python-multipart>=0.0.12` (required for CSV file upload)
* `sse-starlette>=2.1.3` (clean, standards-compliant SSE streaming)
* `google-genai>=1.0.0` (official Google GenAI SDK)
* `google-adk>=1.0.0` (Google ADK 2.0 orchestration — verify exact installed package version at Stage 2 init)
* `numpy>=2.1.0` (fast cosine similarity for in-memory vector memory in Stage 2)
* `pytest>=8.3.0` + `httpx>=0.27.0` (contract & endpoint verification)

### Frontend (`frontend/package.json`)
* `next` (App Router, TypeScript enabled)
* `react` + `react-dom`
* `zustand` (O(1) normalized selector store for 60 FPS Bloodbath updates)
* `tailwindcss`
* `framer-motion` (kinetic Bloodbath animations)
* `lucide-react` (tactical icons)
* `clsx` + `tailwind-merge` (clean conditional styling)

---

## 1.3 Slaying Aggression Levels (`SlayingLevel`) — Product Energy Design

To give the product personality and make live demos interactive, the user chooses one of three aggression modes before launching the pipeline:

| Enum Value | UI Badge Name | Tagline | Disqualification Philosophy | Target Survival Rate (on 50 leads) |
| :--- | :--- | :--- | :--- | :--- |
| `LENIENT` | **Scout** | *"Cast a wider net"* | Kills **only hard blockers**: direct competitor lock-in, wrong non-buyer role, defunct company. Borderline budget/timing leads survive. | ~36%–40% (~18–20 survive) |
| `NORMAL` | **Tactical** | *"Balanced GTM"* | Kills hard blockers **plus** clear ICP mismatches (too small, no cloud/stack match, mild timing friction). | ~24%–28% (~12–14 survive) |
| `RUTHLESS` | **Bloodbath** *(Default)* | *"Protect the domain at all costs"* | Zero mercy. Requires **explicit pain + ideal stack + right seniority + active growth/budget velocity**. Any ambiguity, soft friction, or weak timing = instant kill. | ~14%–16% (~7–8 survive) |

---

## 1.4 Complete Typed Contracts (`backend/app/models/schemas.py` ↔ `frontend/src/types/contracts.ts`)

Every field below must match **1:1** in name, type, and enum values between Python and TypeScript.

### Enums
1. `SlayingLevel`: `"LENIENT" | "NORMAL" | "RUTHLESS"`
2. `ExecutionMode`: `"LIVE" | "SAFE_REPLAY"`
3. `PipelinePhase`: `"IDLE" | "AUDITING" | "ICP_GENERATION" | "HUNTING" | "SLAYING" | "SNIPING" | "READY" | "DISPATCHED" | "ERROR"`
4. `RejectionCategory`:
   * `"COMPETITOR_LOCK_IN"`
   * `"TOO_SMALL"`
   * `"LAYOFFS_FREEZE"`
   * `"WRONG_PERSONA"`
   * `"NO_STACK_FIT"`
   * `"BUILT_IN_HOUSE"`
   * `"NO_URGENCY_SIGNAL"`
5. `ModelId`:
   * `"gemini-4-hydrogen"`
   * `"gemini-3.5-flash-lite"`
   * `"gemini-embedding-2"`
6. `StreamEventType`:
   * `"phase_changed"`
   * `"agent_log"`
   * `"audit_completed"`
   * `"icps_generated"`
   * `"hunter_report"`
   * `"leads_loaded"`
   * `"lead_verdict"`
   * `"email_drafted"`
   * `"telemetry_update"`
   * `"pipeline_completed"`
   * `"pipeline_error"`

### Core Domain Models
1. **`StartupInput`**
   * `product_name: str` (min 2 chars)
   * `product_url: str | None`
   * `description: str` (min 20 chars)
   * `founder_assumptions: str` (what the founder *thinks* their market/buyer is)
   * `slaying_level: SlayingLevel = "RUTHLESS"`
   * `execution_mode: ExecutionMode = "LIVE"`
   * `leads: list[LeadRecord] | None` (if omitted, backend loads `data/leads_50.json`)

2. **`MarketAuditResult`** *(Produced by `gemini-4-hydrogen` + `url_fetcher.py` + optional Gemini Search Grounding)*
   * `market_reality_summary: str` (2–3 crisp sentences grounding reality)
   * `founder_blind_spots: list[str]` (2–3 assumptions challenged/corrected)
   * `sharpened_value_prop: str` (1-line killer positioning statement)
   * `anti_icp_red_flags: list[str]` (explicit rules fed directly into the Slayer!)
   * `market_readiness_score: int` (0–100)
   * `url_scraped_context_used: bool = False`, `search_grounding_used: bool = False`
   * `assumption_gaps: list[AssumptionGap]` (`{ founder_belief, market_reality, severity, strategic_fix }`)
   * `competitor_landscape: list[CompetitorInsight]` (`{ name, positioning_weakness, switching_trigger }`)
   * `buying_objections: list[BuyingObjection]` (`{ objection, buyer_role, counter_angle }`)
   * `readiness_breakdown: ReadinessBreakdown | None` (`{ pain_urgency, icp_clarity, differentiation, timing_fit }`)

3. **`ICPProfile`** *(Generated & embedded via `gemini-embedding-2`)*
   * `id: str` (e.g., `"icp_1"`)
   * `name: str` (e.g., `"High-Growth Series B CTO"`)
   * `target_roles: list[str]`
   * `min_employees: int`
   * `max_employees: int`
   * `required_tech_signals: list[str]`
   * `buying_triggers: list[str]`
   * `instant_disqualifiers: list[str]`
   * `vector_doc_id: str`

3b. **`HunterReport`** *(Produced by `HunterSwarmAgent`)*
   * `hunt_queries: list[HuntQuery]` (`{ source, query_string, signal_target }`)
   * `enriched_sparse_leads: int`, `url_fetches_succeeded: int`, `total_leads_ready: int`

4. **`LeadRecord`** *(Each of the 50 raw leads)*
   * `id: str` (`"lead_01"` … `"lead_50"`)
   * `full_name: str`
   * `role: str`
   * `company: str`
   * `domain: str`
   * `industry: str`
   * `employee_count: int`
   * `funding_stage: str` (`"Bootstrapped" | "Pre-Seed" | "Seed" | "Series A" | "Series B" | "Series C" | "Public"`)
   * `tech_stack: list[str]`
   * `recent_signal: str` (the critical buying or red-flag event)
   * `bio_snippet: str`
   * `email: str`

5. **`SlayerVerdict`** *(Produced per lead by `gemini-3.5-flash-lite` + Stage 2 Hybrid Memory)*
   * `lead_id: str`
   * `survived: bool`
   * `resurrected_by_user: bool = False` *(Improvement #4: human-in-the-loop override)*
   * `rejection_category: RejectionCategory | None` (required when `survived=False`)
   * `headline_tag: str` (max 5 words for UI badge, e.g. `"KILLED: Datadog Lock-In"` or `"SURVIVED: 3x AWS Cost Spike"`)
   * `reasoning: str` (1–2 sentences explaining exact evidence)
   * `matched_icp_id: str | None` (when `survived=True`)
   * `icp_similarity_score: float` (0.0–1.0 from `gemini-embedding-2`)
   * `anti_icp_similarity_score: float` (0.0–1.0 repulsion score from `gemini-embedding-2`)
   * `structural_match_score: float` (0.0–1.0 exact stack/headcount overlap)
   * `qualification_score: int` (0–100 composite fit score powering Improvement #5)
   * `confidence: float` (0.0–1.0)
   * `slaying_level_applied: SlayingLevel`
   * `latency_ms: int`
   * `model_used: ModelId = "gemini-3.5-flash-lite"`

6. **`EmailDraft`** *(Produced per survivor by `gemini-4-hydrogen`)*
   * `lead_id: str`
   * `recipient_name: str`
   * `recipient_email: str`
   * `company: str`
   * `subject: str`
   * `body: str`
   * `cited_survival_signal: str` (exact signal from lead profile — Improvement #1)
   * `email_evidence_phrase: str` (exact substring inside `body` to highlight in UI — Improvement #1)
   * `matched_product_chunk: str` (exact Stage 2 retrieved capability snippet — Improvement #1)
   * `personalization_score: int` (0–100)
   * `approved: bool = True`
   * `status: Literal["DRAFTED", "SENT"] = "DRAFTED"`

7. **`TelemetryMetrics`** *(Live HUD metrics for judges)*
   * `total_leads: int`
   * `processed_leads: int`
   * `killed_count: int`
   * `survived_count: int`
   * `kill_rate_pct: float`
   * `rejection_breakdown: dict[str, int]` (counts per `RejectionCategory`)
   * `model_calls: dict[ModelId, int]`
   * `avg_slayer_latency_ms: float`
   * `elapsed_ms: int`
   * `estimated_saved_spam_hours: float`

8. **`StreamEvent`** *(SSE Envelope)*
   * `event_id: int` (monotonic sequence counter for ordering/replay)
   * `run_id: str`
   * `timestamp_ms: int`
   * `event_type: StreamEventType`
   * `payload: dict[str, Any]` (typed per `event_type` on TS side via discriminated union!)

---

## 1.5 Exact API Endpoints (Stage 1 Contract)

| Method & Path | Purpose | Request | Response |
| :--- | :--- | :--- | :--- |
| `GET /api/health` | Liveness + configured models check | None | `{ status: "ok", models: {...}, default_demo_ready: true }` |
| `GET /api/demo/preset` | Returns default startup + 50 leads for 1-click stage load | None | `{ startup: StartupInput, leads: LeadRecord[] }` |
| `POST /api/leads/parse-csv` | Parses & validates user-uploaded CSV file | `multipart/form-data` (`file`) | `{ count: int, leads: LeadRecord[], warnings: string[] }` |
| `POST /api/pipeline/start` | Starts autonomous 5-step ADK pipeline run | `StartupInput` | `{ run_id: str, stream_url: str }` |
| `GET /api/pipeline/{run_id}/stream` | Live SSE stream of all `StreamEvent`s | Query: `last_event_id?` | `text/event-stream` |
| `GET /api/pipeline/{run_id}/state` | Full JSON snapshot of `RunState` for instant reconnect recovery | None | `RunStateSnapshot` JSON |
| `POST /api/pipeline/{run_id}/dispatch` | Mock-sends approved survivor emails | `{ lead_ids: str[] }` | `{ dispatched_count: int, sent_at: str, receipts: [...] }` |
| `POST /api/pipeline/{run_id}/resurrect/{lead_id}` | Human override: resurrects a killed lead & invokes Sniper (`#4`) | None | `{ verdict: SlayerVerdict, email_draft: EmailDraft }` |
| `GET /api/pipeline/{run_id}/export` | Downloads Survivors CSV or Kill Audit JSON (`#10`) | Query: `format=csv\|json` | File download (`text/csv` or `application/json`) |

---

## 1.6 The 50-Lead Adversarial Dataset Blueprint (`data/leads_50.csv` & `leads_50.json`)

**Default Showcase Product (`data/default_startup.json`):**
* **Product:** **KubeGuard AI** — Autonomous Kubernetes & Cloud FinOps Guardrail that predicts AWS/GCP cost spikes and auto-tunes noisy microservice autoscaling in real time without code changes.
* **Founder's Naive Assumption:** *"Any tech company running cloud servers with a CTO or Engineering Manager needs us."*

**Exact 50-Lead Distribution (Engineered for Realistic Adversarial Triage):**

| Bucket | Count | Signal Pattern Planted in Data | Expected Verdict (`RUTHLESS`) | Expected Verdict (`LENIENT`) |
| :--- | :---: | :--- | :--- | :--- |
| **1. Competitor Lock-In** | **10** | Signed 2–3 yr enterprise deal with Datadog Cloud Cost, Cast.ai, or Kubecost within last 6 months | **KILLED** (`COMPETITOR_LOCK_IN`) | **KILLED** |
| **2. Too Small / No Scale** | **8** | 4–14 total employees, Pre-Seed/Bootstrapped, running single Vercel/Heroku monolith | **KILLED** (`TOO_SMALL`) | **KILLED** |
| **3. Layoffs / Freeze** | **7** | Recent 15–30% layoffs, CFO budget freeze, or acquisition restructuring announced | **KILLED** (`LAYOFFS_FREEZE`) | **KILLED** |
| **4. Wrong Persona** | **7** | People Ops Lead, Brand Designer, Sales Rep, or Junior Frontend Intern (zero infra authority) | **KILLED** (`WRONG_PERSONA`) | **KILLED** |
| **5. Built In-House / Wrong Stack** | **5** | Dedicated 12-person internal FinOps platform team OR pure on-prem bare-metal / Azure mainframe | **KILLED** (`BUILT_IN_HOUSE` / `NO_STACK_FIT`) | **50% KILLED** |
| **6. Borderline Friction** *(Slider-Sensitive)* | **5** | Solid Series A/B CTO (35–80 devs, AWS/EKS), *but* just hired a new VP Infra 2 weeks ago or has mild timing friction | **KILLED** (`NO_URGENCY_SIGNAL`) | **SURVIVED** *(Shows real difference when user switches to Scout/Normal!)* |
| **7. Golden Survivors** | **8** | Series A–C CTOs / VPs of Eng (45–280 employees), AWS + EKS/K8s stack, urgent pain signal (e.g., *"AWS bill jumped 3.2x after launching RAG pipeline"*, *"Complained publicly about K8s OOMKills & over-provisioned GPU nodes"*) | **SURVIVED** | **SURVIVED** |
| **TOTAL** | **50** | — | **42 Killed / 8 Survived (84% Kill Rate)** | **~32 Killed / ~18 Survived** |

---

## 1.7 Stage 1 Step-by-Step Implementation Checklist

When we begin coding Stage 1, execute these exact steps in order:
1. Initialize `.gitignore` and `.env.example` at repo root.
2. Scaffold `/backend` with `pyproject.toml`, `requirements.txt`, Python virtual environment, and `app/config.py`.
3. Implement `backend/app/models/schemas.py` with all Pydantic v2 models, field validators, and enums listed in Section 1.4.
4. Implement `backend/app/scripts/export_schema.py` and run it to generate `contracts/schema_spec.json`.
5. Implement `backend/app/services/lead_loader.py` supporting both JSON preset loading and strict CSV parsing with friendly column mapping (`Employee Count` / `employee_count`, comma-separated `tech_stack`).
6. Generate `data/default_startup.json`, `data/leads_50.csv`, and `data/leads_50.json` matching the exact 7-bucket distribution in Section 1.6 (50 unique realistic names, domains, companies, stacks, and signals—zero duplicates).
7. Implement `backend/app/main.py` with `GET /api/health`, `GET /api/demo/preset`, and `POST /api/leads/parse-csv` + CORS middleware for `http://localhost:3000`.
8. Write `backend/tests/test_stage1_contracts.py` verifying:
   - All 50 leads validate cleanly against `LeadRecord` with 0 missing IDs or duplicate emails.
   - CSV round-trip (`leads_50.csv` → `/api/leads/parse-csv`) produces identical objects to `leads_50.json`.
   - Schema export runs cleanly.
9. Scaffold `/frontend` using Next.js (TypeScript, Tailwind, App Router), install `framer-motion` and `lucide-react`.
10. Create `frontend/src/types/contracts.ts` (exact discriminated union TS mirror of `schemas.py`) and `frontend/src/lib/constants.ts`.
11. Build a minimal `frontend/src/app/page.tsx` connection test confirming Frontend ↔ Backend `/api/health` + `/api/demo/preset` fetch succeeds with full type safety.

### Stage 1 Exit Gate (Definition of Done)
- `pytest` passes 100% on contract & 50-lead CSV validation.
- `npm run build` / `tsc --noEmit` passes with zero TypeScript errors.
- `GET /api/demo/preset` returns the startup + 50 leads in `< 20ms`.

---

# STAGE 2: FINALIZED IMPLEMENTATION SPECIFICATION — Vector Memory & Hybrid Context Engine
*(Follow step-by-step during implementation — zero guesswork required)*

## 2.1 Locked Stage 2 Architecture & Policy

| Component | Locked Design |
| :--- | :--- |
| **Vector Engine** | Pure In-Memory L2-Normalized NumPy (`float32` matrix + metadata dict), isolated per `run_id` |
| **Embedding Model & Dims** | `gemini-embedding-2` with **768-dim Matryoshka truncation** (`output_dimensionality=768`) + explicit Gemini `task_type` |
| **Batching** | Chunked batch API calls (`batch_size=25` texts per request → 50 leads embedded in 2 calls) |
| **Bounded TTL Cache** | SHA-256 disk + memory cache with **6-hour max TTL (`21,600s`)** & **1,000-entry max cap** (LRU eviction, atomic write, never overloads RAM/disk) |
| **Matching Formula** | Dual-Polarity Hybrid Score: `60% ICP Cosine + 25% Structural Match − 15% Anti-ICP Cosine` |
| **Product Chunking** | Semantic Section Chunking (`CORE_PITCH`, `PAIN_SOLVED`, `TECH_CAPABILITY`, `PROOF_POINT`, `ANTI_ICP`) |
| **Failure Policy (Strict)** | On cache miss + live API failure (after 1 retry): **NO fake vectors.** Raise `GeminiAPIUnavailableError` surfacing a clear message (*"Gemini API limit reached or overloaded. Please wait a moment and try again."*) |

---

## 2.2 Stage 2 File Additions (`backend/`)

```text
backend/app/
├── memory/
│   ├── __init__.py
│   ├── exceptions.py          # GeminiAPIUnavailableError (429 / overload / timeout)
│   ├── cache.py               # BoundedTTLEmbeddingCache (6h TTL, max 1000 entries, atomic JSON/NPZ)
│   ├── embedder.py            # GeminiEmbedder (gemini-embedding-2, 768d MRL, batch=25, retry=1)
│   ├── chunker.py             # Semantic section chunker for Startup + MarketAuditResult
│   ├── structural_matcher.py  # Tech-stack alias normalization + headcount/role structural score
│   ├── vector_store.py        # HybridMemoryStore (NumPy float32 L2-normalized store)
│   └── registry.py            # Per-run_id MemoryRegistry (max 20 runs, 6h TTL cleanup)
└── tests/
    └── test_stage2_memory.py  # Unit tests: TTL expiry, LRU cap, error propagation, hybrid math
```

---

## 2.3 Detailed Module Specifications

### A. `exceptions.py` — Explicit Rate-Limit & Overload Error
* Define `GeminiAPIUnavailableError(Exception)`:
  * Fields: `user_message: str`, `status_code: int | None`, `raw_error: str`.
  * Standard user-facing message when `429`, `RESOURCE_EXHAUSTED`, `503`, `overloaded`, or timeout occurs after retry:
    > `"Gemini embedding API limit reached or service is temporarily overloaded. Please wait a short while and try again."`
  * Upstream pipeline catches this and emits a `pipeline_error` SSE event so the UI displays a clear banner instead of silently proceeding with garbage vectors.

### B. `cache.py` — `BoundedTTLEmbeddingCache` (6-Hour TTL & System Overload Guard)
* **Cache Key:** `sha256(f"{model_id}:{dim}:{task_type}:{normalized_text}".encode("utf-8")).hexdigest()`
* **Disk Format (`data/.emb_cache.json`):**
  ```json
  {
    "version": 1,
    "dim": 768,
    "entries": {
      "<sha256>": { "created_at": 1732640000.0, "last_used": 1732640000.0, "vector": [0.012, ...] }
    }
  }
  ```
* **Hard Resource Caps (Preventing System Overload):**
  1. `ttl_seconds: int = 21600` (**Max 6 hours** — any entry with `now - created_at > 21600` is treated as expired, evicted on access, and purged before disk flush).
  2. `max_entries: int = 1000` (1000 × 768 float32s ≈ **~3.1 MB RAM**, ~7 MB JSON max). If inserting exceeds `1000`, evict expired items first, then oldest-`last_used` entries (`OrderedDict` LRU).
  3. `max_text_bytes: int = 16384` (texts larger than 16 KB are rejected with `ValueError` before hashing/API call).
  4. **Exact Interface:**
     * `async def get_many(keys: list[str]) -> tuple[dict[str, np.ndarray], list[int]]` (returns `{key: vec}` hits + missing/expired indices)
     * `async def put_many(items: dict[str, np.ndarray], flush: bool = True) -> None`
     * `def purge_expired() -> int`
  5. **Concurrency & Safe Disk Persistence:**
     * Protected by `asyncio.Lock`.
     * **Batch Flush:** Writes to `data/.emb_cache.json` *only* once at the end of `embed_batch()` when at least 1 new entry was added (never writes inside per-item loops).
     * **Atomic Write:** Writes to `data/.emb_cache.json.tmp` and swaps via `os.replace()` so a crash never corrupts the cache file.
     * On startup/load, immediately drops any entries older than 6 hours and enforces `max_entries`.

### C. `embedder.py` — `GeminiEmbedder` (`gemini-embedding-2`)
* **Config:** `model="gemini-embedding-2"`, `output_dimensionality=768`, `batch_size=25`, `max_retries=1`.
* **Supported `task_type` values:**
  * `"RETRIEVAL_DOCUMENT"` for product chunks, ICP profiles, and Anti-ICP rules.
  * `"SEMANTIC_SIMILARITY"` (or `"RETRIEVAL_QUERY"`) for lead profiles and Sniper grounding queries.
  * *(Note: Verify exact `google-genai` SDK enum string at Stage 2 implementation time.)*
* **Execution Flow (`embed_texts(texts, task_type)`):**
  1. Compute SHA-256 keys for all input texts.
  2. Query `BoundedTTLEmbeddingCache` (returns valid non-expired vectors + list of cache-miss indices).
  3. If `0` cache misses → return L2-normalized `np.ndarray` immediately (`0` API calls).
  4. Partition cache-miss texts into batches of `25`.
  5. For each batch, call `google-genai` `embed_content` with `EmbedContentConfig(output_dimensionality=768, task_type=task_type)`.
     * On transient network/`429`/`503`: wait `1.5s` (exponential backoff, `1` retry max so we don't stall the UI or hammer an overloaded API).
     * If retry fails: **Raise `GeminiAPIUnavailableError`** (never return zero/random/fake hash vectors!).
  6. L2-normalize returned vectors: `vec = vec / np.maximum(np.linalg.norm(vec), 1e-12)`.
  7. Store new vectors in `BoundedTTLEmbeddingCache` with `created_at = time.time()` and flush atomically once.

### D. `chunker.py` — Semantic Product & Audit Chunker
Converts `StartupInput` + `MarketAuditResult` into 5–8 focused `KnowledgeChunk` objects (kept under ~120 words each for surgical Sniper retrieval):
1. `CORE_PITCH`: Product name + `sharpened_value_prop` + core summary.
2. `PAIN_SOLVED`: Extracted pain points + market reality summary from `MarketAuditResult`.
3. `TECH_CAPABILITY`: Technical differentiators parsed from `description` (split cleanly by sentences/bullets if >120 words).
4. `PROOF_POINT` / `BLIND_SPOT_COUNTER`: How the product addresses `founder_blind_spots`.
5. `ANTI_ICP`: Each string in `MarketAuditResult.anti_icp_red_flags` becomes an indexed `anti_icp` vector document!

### E. `structural_matcher.py` — Exact Tech & Headcount Signal Scorer
Computes deterministic `structural_match_score` ($S_{\text{struct}} \in [0.0, 1.0]$) against an `ICPProfile`:
* **Tech Stack Alias Map:** Normalizes common variants before set intersection (e.g., `{"k8s": "kubernetes", "eks": "kubernetes", "gke": "kubernetes", "aks": "kubernetes", "aws ec2": "aws", "datadog apm": "datadog"}`).
* **Sub-scores:**
  1. `stack_overlap` (weight `0.55`): `|lead_stack_norm ∩ icp_required_norm| / max(1, len(icp_required_norm))` (capped at `1.0`).
  2. `size_fit` (weight `0.30`): `1.0` if `min_employees <= employee_count <= max_employees`, decaying linearly outside the window (`0.0` if `< 0.5 * min_employees` or `> 3 * max_employees`).
  3. `role_seniority_fit` (weight `0.15`): Token match against `icp.target_roles` (e.g., `CTO`, `VP Engineering`, `Head of Platform`, `Staff Infra`).

### F. `vector_store.py` — `HybridMemoryStore`, Serialization & Dual-Polarity Math
Stores 4 typed partitions in memory per `run_id`:
* `product_chunks`: `(N_prod, 768)` float32 matrix + `KnowledgeChunk` metadata
* `icps`: `(3, 768)` float32 matrix + `ICPProfile` list
* `anti_icps`: `(M_anti, 768)` float32 matrix + red-flag strings
* `leads`: `(50, 768)` float32 matrix + `LeadRecord` list

**Deterministic Embedding Text Templates (So Vectors Align Cleanly):**
* `serialize_icp(icp)`: `f"Target ICP: {icp.name}. Roles: {', '.join(icp.target_roles)}. Company size: {icp.min_employees}-{icp.max_employees}. Required stack: {', '.join(icp.required_tech_signals)}. Buying triggers: {'; '.join(icp.buying_triggers)}."`
* `serialize_lead(lead)`: `f"Role: {lead.role} at {lead.company} ({lead.industry}, {lead.employee_count} employees, {lead.funding_stage}). Stack: {', '.join(lead.tech_stack)}. Recent signal: {lead.recent_signal}. Bio: {lead.bio_snippet}"`

**Typed Output Models (Consumed by Stage 3 ADK Agents):**
* `HybridMatchContext`: `{ lead_id: str, best_icp: ICPProfile, icp_similarity_score: float, anti_icp_similarity_score: float, matched_anti_icp_rule: str, structural_match_score: float, prior_score_100: int }`
* `SniperGrounding`: `{ lead_id: str, top_product_chunks: list[KnowledgeChunk], matched_icp: ICPProfile }`

**Lead-to-ICP Dual-Polarity Hybrid Scoring (`async def index_and_score_leads(...) -> dict[str, HybridMatchContext]`):**
Computed via vectorized NumPy matrix multiplication in `< 1ms`:
1. `icp_sims = leads_matrix @ icps_matrix.T` → shape `(50, 3)`
   * `best_icp_idx = argmax(icp_sims, axis=1)`
   * `icp_sim = clip(max(icp_sims, axis=1), 0.0, 1.0)`
2. `anti_sims = leads_matrix @ anti_icps_matrix.T` → shape `(50, M_anti)` (if `M_anti == 0`, default `0.0`)
   * `anti_icp_sim = clip(max(anti_sims, axis=1), 0.0, 1.0)`
   * `matched_anti_icp_rule = anti_icp_strings[argmax(anti_sims, axis=1)]`
3. `struct_score = structural_matcher.score(lead, best_icp)` $\in [0.0, 1.0]$
4. **Raw Dual-Polarity Hybrid Score:**
   $$\text{raw\_hybrid} = 0.60 \cdot \text{icp\_sim} + 0.25 \cdot \text{struct\_score} - 0.15 \cdot \text{anti\_icp\_sim}$$
5. **Normalized Prior Score (`0–100`):**
   $$\text{prior\_score\_100} = \text{round}(\text{clip}(\text{raw\_hybrid}, 0.0, 1.0) \times 100)$$

*(Note: This mathematical prior is injected into the Slayer agent prompt and fused with the Slayer LLM's verdict to produce the final `qualification_score` and `icp_similarity_score`.)*

**Sniper Context Retrieval (`async def get_sniper_grounding(lead: LeadRecord, survival_reason: str, matched_icp: ICPProfile, top_k: int = 2) -> SniperGrounding`):**
* Embeds `f"{lead.role} at {lead.company} ({', '.join(lead.tech_stack)}): {lead.recent_signal} | {survival_reason}"` using `RETRIEVAL_QUERY` / `SEMANTIC_SIMILARITY` (cached for 6h).
* Runs cosine similarity against `product_chunks` (`product_chunks_matrix @ query_vec`).
* Returns top-2 matching `KnowledgeChunk`s + `matched_icp` (total `< 300` tokens) so Sniper cites exact matching capabilities (**Improvement #1**).

### G. `registry.py` — `MemoryRegistry` (Per-Run Isolation & RAM Protection)
* Stores `{ run_id: (created_at, HybridMemoryStore) }` in an `OrderedDict`.
* **Max Active Runs:** `20` (oldest evicted automatically).
* **Max Run TTL:** `21600` seconds (**6 hours**) — expired runs purged on lookup/creation so FastAPI never leaks memory across demos.

---

## 2.4 Stage 2 Step-by-Step Implementation Checklist

1. Create `backend/app/memory/exceptions.py` with `GeminiAPIUnavailableError`.
2. Create `backend/app/memory/cache.py` implementing `BoundedTTLEmbeddingCache` (`ttl=21600`, `max_entries=1000`, `asyncio.Lock`, atomic `os.replace`, auto-purge on load & read).
3. Create `backend/app/memory/embedder.py` implementing `GeminiEmbedder` (`gemini-embedding-2`, `dim=768`, `batch_size=25`, `retry=1`, raises `GeminiAPIUnavailableError` on live miss failure).
4. Create `backend/app/memory/chunker.py` implementing semantic section chunking for `StartupInput` + `MarketAuditResult`.
5. Create `backend/app/memory/structural_matcher.py` implementing stack alias map + size/role structural scoring.
6. Create `backend/app/memory/vector_store.py` implementing `HybridMemoryStore` (NumPy L2 matrix math, dual-polarity scoring, Sniper top-2 retrieval).
7. Create `backend/app/memory/registry.py` implementing `MemoryRegistry` (`max_runs=20`, `ttl=21600`).
8. Write `backend/tests/test_stage2_memory.py` verifying:
   - Cache respects 6-hour TTL (expired items trigger re-embed / miss).
   - Cache enforces 1,000-entry max cap via LRU eviction.
   - When cache misses and mocked Gemini client throws `429`/overload after 1 retry, `GeminiAPIUnavailableError` is raised cleanly (no fake vectors returned).
   - Dual-polarity scoring ranks a golden survivor strictly higher than a competitor-locked or layoff lead.
   - `MemoryRegistry` isolates `run_id`s and evicts expired/excess runs.

### Stage 2 Exit Gate (Definition of Done)
- All Stage 2 unit tests pass (`pytest backend/tests/test_stage2_memory.py`).
- Live smoke test embeds the 50 demo leads in `<= 2` batched `gemini-embedding-2` calls, writes `data/.emb_cache.json` atomically, and hits `0ms` cache on second run.

---

# STAGE 3: FINALIZED IMPLEMENTATION SPECIFICATION — Google ADK 2.0 Pipeline & Slayer Engine
*(Follow step-by-step during implementation — zero guesswork required)*

## 3.1 Locked Stage 3 Architecture & Policy

| Component | Locked Design |
| :--- | :--- |
| **ADK Topology** | Hybrid ADK 2.0: `SequentialAgent` + `InMemorySessionService` + `LlmAgent`s (`Auditor`, `ICPEngine`, `Sniper`) + Custom ADK `BaseAgent`s (`HunterSwarmAgent`, `SlayerSwarmAgent`) |
| **Model Routing** | `MarketAuditor` (`gemini-4-hydrogen`) → `ICPEngine` (`gemini-4-hydrogen` + `gemini-embedding-2`) → `Hunter` (`gemini-3.5-flash-lite` sparse-only) → `Slayer` (`gemini-3.5-flash-lite`) → `Sniper` (`gemini-4-hydrogen`) |
| **Gentle Concurrency** | **Gentle Adaptive Pool:** `asyncio.Semaphore(5)` + `60ms` inter-task launch stagger + shared cooldown lock on `429`/`503` + max `2` jittered retries (`1.5s`, `3.5s`) → finishes 50 leads in ~4.5–5.5s reliably without quota spikes |
| **Anti-Bias Schema** | Schema-ordered structured output: `disqualifier_signals_found` → `rejection_category` → `reasoning` → `survived: bool` → `headline_tag` |
| **Hunter Behavior** | Fast deterministic validation on clean 50-lead preset/CSV; invokes `gemini-3.5-flash-lite` batch enrichment (size 10) *only* when user CSV lacks `tech_stack` or `recent_signal` |
| **Sniper & Resurrect** | Stage 2 top-2 product chunks + verbatim `email_evidence_phrase` substring check; on-demand `POST /resurrect/{lead_id}` calls Sniper live for overridden kills |
| **Failure Policy** | After gentle retries exhaust (`429`/overload/timeout), raise `GeminiAPIUnavailableError` — never fabricate AI verdicts |

---

## 3.2 Stage 3 File Additions (`backend/`)

```text
backend/app/
├── agents/
│   ├── __init__.py
│   ├── prompts.py             # Versioned system prompts + SlayingLevel tiered rubrics
│   ├── structured_outputs.py  # LLM-facing Pydantic schemas (think-first field order!)
│   ├── rate_limiter.py        # GentleAdaptiveExecutor (Semaphore(5), jitter, cooldown, retry=2)
│   ├── auditor_agent.py       # ADK LlmAgent: MarketAuditor (gemini-4-hydrogen)
│   ├── icp_agent.py           # ADK LlmAgent: ICPEngine (gemini-4-hydrogen) + Stage 2 indexing
│   ├── hunter_agent.py        # ADK BaseAgent: HunterSwarmAgent (validate + sparse flash-lite enrich)
│   ├── slayer_agent.py        # ADK BaseAgent: SlayerSwarmAgent (50-lead adversarial triage)
│   ├── sniper_agent.py        # ADK LlmAgent + service: Sniper (gemini-4-hydrogen + Resurrect)
│   └── pipeline.py            # ADK SequentialAgent + Runner + SSE callback bridge
└── tests/
    └── test_stage3_agents.py  # Unit tests: schema ordering, rubric levels, gentle retry, Sniper span check
```

---

## 3.3 Detailed Module Specifications

### A. `rate_limiter.py` — `GentleAdaptiveExecutor` (High-Reliability Concurrency)
Designed specifically so 50 parallel `flash-lite` calls **never slam** the Gemini API:
* **Concurrency Cap:** `asyncio.Semaphore(5)` (at most 5 in-flight requests at any instant).
* **Launch Stagger:** `60ms` delay between initial task dispatches so requests form a smooth stream instead of a 0ms burst.
* **Shared Cooldown Gate:** An `asyncio.Event` (`cooldown_clear`, initially set). If *any* worker hits a `429` or `503`:
  1. It temporarily clears `cooldown_clear`, waits `backoff` (`1.5s` on attempt 1, `3.5s` on attempt 2, plus `0–300ms` random jitter), then re-sets `cooldown_clear`—automatically pausing sibling workers from piling onto a throttled endpoint!
  2. Max `2` retries. If attempt 3 still fails (or non-transient auth/invalid error occurs), raises `GeminiAPIUnavailableError`.
* **Helper Signature:**
  `async def run_bounded_stream(items: list[T], worker_fn: Callable[[T], Awaitable[R]]) -> AsyncIterator[tuple[T, R]]`
  Uses `asyncio.as_completed` under the semaphore so Stage 4 receives verdicts the moment each lead finishes (~4.5s total for 50 leads).

### B. `structured_outputs.py` — Think-First LLM Schemas
1. **`_SlayerLLMResponse`** *(Converted to public `SlayerVerdict` after scoring fusion)*:
   Field order is strictly enforced so `flash-lite` reasons adversarially *before* deciding:
   * `disqualifier_signals_found: list[str]` (empty if none)
   * `tier_triggered: Literal["NONE", "TIER_1_HARD", "TIER_2_ICP_FIT", "TIER_3_FRICTION"]`
   * `rejection_category: RejectionCategory | None`
   * `reasoning: str` (max 2 sharp sentences citing lead facts)
   * `survived: bool`
   * `headline_tag: str` (strict `<= 5` words, e.g. `"KILLED: Datadog Lock-In"` or `"SURVIVED: 3.2x AWS Spike"`)
   * `confidence: float` (`0.0–1.0`)
2. **`_SniperLLMResponse`** *(Converted to `EmailDraft`)*:
   * `cited_survival_signal: str`
   * `subject: str` (max 9 words, lowercase/peer style, zero spam words)
   * `body: str` (`75–130` words, must weave in `cited_survival_signal` + retrieved Stage 2 capability)
   * `email_evidence_phrase: str` (exact verbatim substring copied from `body` referencing the survival hook)
   * `personalization_score: int` (`0–100`)

### C. `prompts.py` — Tiered Adversarial Slayer Rubric (`LENIENT` / `NORMAL` / `RUTHLESS`)
Injects **both** the static Tier rules **and** the dynamic `MarketAuditResult.anti_icp_red_flags` from Step 1:
* **Tier 1 — Hard Blockers (KILL in ALL modes):**
  * `COMPETITOR_LOCK_IN`: Recent multi-year contract or deep lock-in with direct competitor.
  * `WRONG_PERSONA`: Non-buyer role (HR, Designer, Sales Rep, Intern, zero budget/infra authority).
  * `LAYOFFS_FREEZE`: Active layoffs, hiring freeze, or M&A freeze.
* **Tier 2 — ICP & Stack Fit (KILL in `NORMAL` & `RUTHLESS`; PASS in `LENIENT` unless zero relevance):**
  * `TOO_SMALL`: `< min_employees` or pre-scale prototype with no infra complexity.
  * `NO_STACK_FIT` / `BUILT_IN_HOUSE`: Incompatible stack (on-prem mainframe only) or large internal platform team already built it.
* **Tier 3 — Momentum & Ambiguity (KILL ONLY in `RUTHLESS`):**
  * `NO_URGENCY_SIGNAL`: Right title & decent stack, *but* lacks urgent trigger, just hired new leadership in transition, or Stage 2 `prior_score_100 < 68`.
* **Runtime Rule:** If `SlayingLevel == RUTHLESS`, default posture is **"REJECT unless undeniable buying pain + ICP fit exists."**

### D. Step-by-Step ADK Agents
1. **`MarketAuditorAgent` (`auditor_agent.py` — `gemini-4-hydrogen`):**
   * ADK `LlmAgent(name="market_auditor", model="gemini-4-hydrogen", output_schema=MarketAuditResult, output_key="market_audit")`.
   * Challenges founder assumptions and produces `anti_icp_red_flags` (4–5 concrete kill rules).
2. **`ICPEngineAgent` (`icp_agent.py` — `gemini-4-hydrogen` + Stage 2):**
   * ADK `LlmAgent(name="icp_engine", model="gemini-4-hydrogen", output_schema=_ICPBatchOutput, output_key="icps")` generates exactly 3 distinct `ICPProfile`s from `session.state["market_audit"]`.
   * Immediately indexes `product_chunks`, `icps`, and `anti_icps` into `HybridMemoryStore` via `gemini-embedding-2`.
3. **`HunterSwarmAgent` (`hunter_agent.py` — ADK `BaseAgent`):**
   * Reads `leads` from `session.state`.
   * **Fast Path (Preset / Clean CSV):** Validates all 50 rows in `< 5ms`.
   * **Enrichment Path (Sparse User CSV):** If `> 20%` of leads have empty `tech_stack` or `recent_signal`, runs `GentleAdaptiveExecutor` with `gemini-3.5-flash-lite` in batches of 10 to normalize/infer tags.
   * Calls `memory_store.index_and_score_leads(leads)` → stores `dict[lead_id, HybridMatchContext]` in `session.state["hybrid_priors"]`.
4. **`SlayerSwarmAgent` (`slayer_agent.py` — ADK `BaseAgent`, `gemini-3.5-flash-lite`):**
   * Reads `market_audit.anti_icp_red_flags`, `slaying_level`, and `hybrid_priors`.
   * Executes all 50 leads via `GentleAdaptiveExecutor` (`Semaphore(5)`, stagger `60ms`).
   * **Qualification Score Fusion (`0–100`):**
     * If `survived == True`: `score = round(0.40 * prior_score_100 + 0.60 * (confidence * 100))` (clamped `65–99`)
     * If `survived == False`: `score = round(0.40 * prior_score_100 + 0.60 * ((1 - confidence) * 100))` (clamped `4–62`)
   * Emits each `SlayerVerdict` immediately to the Stage 4 SSE event callback.
5. **`SniperAgent` (`sniper_agent.py` — `gemini-4-hydrogen`):**
   * Filters `survived == True` leads (`~8` leads).
   * For each survivor (with `Semaphore(4)` gentle concurrency):
     1. Calls `memory_store.get_sniper_grounding(lead, verdict.reasoning, matched_icp, top_k=2)`.
     2. Invokes `gemini-4-hydrogen` with `_SniperLLMResponse` schema.
     3. **Deterministic Span Verifier:** Checks `email_evidence_phrase in body` (case-insensitive fallback match if capitalization differs; if still missing, falls back to highlighting the sentence containing `cited_survival_signal` so UI tracing `#1` never breaks).
   * **Exposes `resurrect_single_lead(run_id, lead_id)`:** Invokes the exact same grounding + Sniper logic on-demand for a user-overridden killed lead, sets `verdict.survived = True`, `verdict.resurrected_by_user = True`, and returns `(updated_verdict, email_draft)`.

### E. `pipeline.py` — ADK `SequentialAgent` & Replay Boundary
* Builds ADK `SequentialAgent(name="leadslayer_pipeline", sub_agents=[auditor_agent, icp_agent, hunter_agent, slayer_agent, sniper_agent])` executed via `Runner` + `InMemorySessionService`.
* **Replay Short-Circuit (`ExecutionMode.SAFE_REPLAY`):** Checked cleanly at the `PipelineOrchestrator` entry point—streams pre-recorded events from `data/replay_snapshot.json` into the exact same Stage 4 SSE bus so the UI code has zero special cases.

---

## 3.4 Stage 3 Step-by-Step Implementation Checklist

1. Verify exact `google-adk` & `google-genai` imports (`LlmAgent`, `BaseAgent`, `SequentialAgent`, `Runner`, `InMemorySessionService`) in the Stage 1 venv.
2. Implement `backend/app/agents/structured_outputs.py` with think-first field ordering.
3. Implement `backend/app/agents/prompts.py` with tiered rubrics (`LENIENT`, `NORMAL`, `RUTHLESS`) and Sniper evidence rules.
4. Implement `backend/app/agents/rate_limiter.py` (`GentleAdaptiveExecutor`: `Semaphore(5)`, `60ms` stagger, shared cooldown gate, 2 retries → `GeminiAPIUnavailableError`).
5. Implement `auditor_agent.py`, `icp_agent.py`, `hunter_agent.py`, `slayer_agent.py`, `sniper_agent.py` (including `resurrect_single_lead`), and `pipeline.py`.
6. Write `backend/tests/test_stage3_agents.py` (using mocked Gemini responses) verifying:
   - Think-first schema order in `SlayerLLMResponse`.
   - `RUTHLESS` kills Tier 1+2+3 borderline leads while `LENIENT` lets Tier 3 pass.
   - `GentleAdaptiveExecutor` triggers shared cooldown on `429` and raises `GeminiAPIUnavailableError` after 2 failed retries.
   - Sniper span verifier guarantees `email_evidence_phrase` resolves inside `body`.
   - `resurrect_single_lead` flips verdict + generates grounded `EmailDraft`.

### Stage 3 Exit Gate (Definition of Done)
- All Stage 3 unit tests pass (`pytest backend/tests/test_stage3_agents.py`).
- End-to-end CLI smoke test on `data/default_startup.json` + `data/leads_50.json` completes in `RUTHLESS` mode with ~40–44 kills and ~6–10 grounded Sniper emails in `< 15 seconds` total.

---

# STAGE 4: FINALIZED IMPLEMENTATION SPECIFICATION — SSE Streaming Bus, Pacing & Telemetry
*(Follow step-by-step during implementation — zero guesswork required)*

## 4.1 Locked Stage 4 Architecture & Policy

| Component | Locked Design |
| :--- | :--- |
| **Execution Lifecycle** | Decoupled background `asyncio.Task` managed by `RunManager` — survives browser refresh/Wi-Fi blinks |
| **SSE Transport** | `sse-starlette` (`EventSourceResponse`) with monotonic `id`, `event`, `data`, `15s` keepalive ping, and `Last-Event-ID` replay |
| **Snapshot Recovery** | `GET /api/pipeline/{run_id}/state` returns full `RunStateSnapshot` for instant browser re-hydration |
| **Bloodbath Pacing (`#9`)** | Dual-Lane Adaptive Pacing: `0ms` for Phase/Audit/ICP/Email/Error; `~90ms` cascade for `lead_verdict` (accelerating to `25ms` if queue backlog `> 25`) |
| **Telemetry Sync (`#6`)** | `TelemetryAggregator` updates counts on every verdict/draft/phase change — zero redundant polling timers |
| **Authoritative Exports (`#4, #10`)** | `RunState` is single source of truth; `resurrect` & `dispatch` mutate `RunState`, and `GET /export?format=csv|json` builds directly from `RunState` |
| **Resource Limits** | Max `20` runs in `RunManager` (`OrderedDict` LRU) with `6-hour` TTL (`21,600s`) matching Stage 2 |

---

## 4.2 Stage 4 File Additions (`backend/`)

```text
backend/app/
├── streaming/
│   ├── __init__.py
│   ├── telemetry.py           # TelemetryAggregator (kill/survive, autopsy breakdown, model calls)
│   ├── event_bus.py           # EventStreamBus (monotonic event_id, replay history, subscriber queues)
│   ├── pacer.py               # DualLanePacer (0ms fast lane vs ~90ms/25ms adaptive Bloodbath lane)
│   ├── run_manager.py         # RunState + RunManager (max 20 runs, 6h TTL, asyncio.Task lifecycle)
│   └── exporter.py            # RFC-4180 Survivors CSV + Forensic Kill Audit JSON builder
├── routers/
│   ├── __init__.py
│   └── pipeline_router.py     # /start, /stream, /state, /resurrect/{lead_id}, /dispatch, /export
└── tests/
    └── test_stage4_streaming.py  # Unit tests: replay Last-Event-ID, pacing, error close, export sync
```

---

## 4.3 Detailed Module Specifications

### A. `telemetry.py` — `TelemetryAggregator`
Maintains live `TelemetryMetrics` per `run_id`:
* `record_model_call(model_id: ModelId)` — increments `model_calls[model_id]`.
* `record_verdict(verdict: SlayerVerdict)` — updates `processed_leads`, `killed_count` / `survived_count`, `kill_rate_pct`, `rejection_breakdown[verdict.rejection_category]`, and running `avg_slayer_latency_ms` + `estimated_saved_spam_hours` (`killed_count * 0.25` hrs saved).
* `record_resurrection(old_category: RejectionCategory | None)` — decrements `killed_count` and `rejection_breakdown[old_category]`, increments `survived_count`, recalculates `kill_rate_pct` (`#4`).
* `snapshot() -> TelemetryMetrics` — returns immutable Pydantic copy for inclusion in SSE payloads.

### B. `event_bus.py` — `EventStreamBus`
Thread/async-safe per-run broadcast bus with replay:
* `history: list[StreamEvent]` (bounded safely to `<= 500` events per run).
* `subscribers: set[asyncio.Queue[StreamEvent | None]]`.
* `closed: bool = False`, `terminal_event_type: StreamEventType | None = None`.
* **Exact Methods:**
  * `async def publish(event_type: StreamEventType, payload: dict[str, Any]) -> StreamEvent`: increments monotonic `_seq`, appends to `history`, fans out via `put_nowait` to all active subscriber queues.
  * `async def close() -> None`: sets `closed = True`, pushes `None` sentinel to every subscriber queue.
  * `async def subscribe(last_event_id: int | None = None) -> AsyncIterator[StreamEvent]`:
    1. Immediately yields all `ev` in `history` where `ev.event_id > (last_event_id or 0)`.
    2. If `closed` already, returns cleanly without hanging.
    3. Otherwise registers a queue, yields live events until `None` sentinel or client disconnect, and removes queue in `finally:`.

### C. `pacer.py` — `DualLanePacer` (Improvement `#9`)
Prevents bursty clumps on screen while keeping total runtime tight:
* **Fast Lane (`emit_immediate`):** `phase_changed`, `agent_log`, `audit_completed`, `icps_generated`, `leads_loaded`, `email_drafted`, `pipeline_completed`, `pipeline_error` → calls `bus.publish()` with **`0ms` delay**.
* **Dramatic Bloodbath Lane (`enqueue_verdict` + `drain_task`):**
  * ADK `SlayerSwarmAgent` pushes `(verdict, telemetry_snapshot)` into an `asyncio.Queue`.
  * Background drainer pops items and publishes `lead_verdict` (with bundled `telemetry` field) at:
    * `90ms` delay when `queue.qsize() <= 25`
    * `25ms` delay when `queue.qsize() > 25` (adaptive catch-up!)
  * `await pacer.flush()` waits until the last verdict finishes draining *before* transitioning to `SNIPING`, ensuring all 50 slashes land cleanly on screen before Survivor cards expand!

### D. `run_manager.py` — `RunState` & `RunManager`
* **`RunState` Fields:** `run_id`, `created_at`, `startup_input`, `phase`, `market_audit`, `icps`, `leads`, `verdicts: dict[str, SlayerVerdict]`, `emails: dict[str, EmailDraft]`, `telemetry: TelemetryAggregator`, `bus: EventStreamBus`, `pacer: DualLanePacer`, `task: asyncio.Task | None`, `error_message: str | None`.
* **Lifecycle Safety:**
  1. `start_run(startup_input)`: purges expired runs (`> 6h`), enforces `max_runs=20`, spawns background `asyncio.create_task(_execute_pipeline_safe(run_state))`.
  2. `_execute_pipeline_safe`: wraps Stage 3 `PipelineOrchestrator.run(run_state)` in `try/except`:
     * Catches `GeminiAPIUnavailableError` → publishes `pipeline_error` with exact friendly message (*"Gemini API limit reached or overloaded..."*) + closes bus.
     * Catches unexpected `Exception` → logs traceback, publishes sanitized `pipeline_error`, sets `phase = ERROR`, closes bus.
     * On normal finish → flushes pacer, sets `phase = READY`, publishes `pipeline_completed`, closes bus.
  3. `resurrect_lead(run_id, lead_id)` (`#4`): calls Stage 3 `sniper_agent.resurrect_single_lead()`, updates `run_state.verdicts[lead_id]`, stores `run_state.emails[lead_id]`, updates `telemetry.record_resurrection()`, and returns `{ verdict, email_draft }`.
  4. `dispatch_emails(run_id, lead_ids)`: marks matching `EmailDraft.status = "SENT"`, updates `run_state.phase = DISPATCHED`, returns simulated receipts.

### E. `exporter.py` — Authoritative Export Builder (`#10`)
* **`build_survivors_csv(run_state) -> str`:** Using Python `csv.writer` (`io.StringIO`), exports only leads with `verdicts[id].survived == True` (including resurrected ones!):
  `lead_id, full_name, role, company, email, employee_count, qualification_score, icp_similarity_score, resurrected_by_user, matched_icp_id, cited_survival_signal, email_subject, email_body, dispatch_status`.
* **`build_kill_audit_json(run_state) -> dict`:** Full forensic report containing `startup`, `market_audit`, `icps`, `telemetry`, and every lead paired with its `SlayerVerdict` + `EmailDraft` (if survived).

### F. `pipeline_router.py` — Mounted Endpoints (`/api/pipeline/...`)
* `POST /api/pipeline/start` → `202 Accepted` `{ run_id, stream_url }`
* `GET /api/pipeline/{run_id}/stream` → `EventSourceResponse` reading `Last-Event-ID` header (or `?last_event_id=` query param), `ping=15` seconds
* `GET /api/pipeline/{run_id}/state` → `RunStateSnapshot` JSON
* `POST /api/pipeline/{run_id}/resurrect/{lead_id}` → `{ verdict, email_draft, telemetry }`
* `POST /api/pipeline/{run_id}/dispatch` → `{ dispatched_count, sent_at, receipts }`
* `GET /api/pipeline/{run_id}/export` (`format=csv|json`) → `Response` with `Content-Disposition: attachment; filename="leadslayer_{run_id}_..."`

---

## 4.4 Stage 4 Step-by-Step Implementation Checklist

1. Implement `backend/app/streaming/telemetry.py` (`TelemetryAggregator`).
2. Implement `backend/app/streaming/event_bus.py` (`EventStreamBus` with `Last-Event-ID` replay + sentinel close).
3. Implement `backend/app/streaming/pacer.py` (`DualLanePacer` with `90ms`/`25ms` adaptive drain & `flush()`).
4. Implement `backend/app/streaming/exporter.py` (RFC-4180 CSV + JSON Audit builders).
5. Implement `backend/app/streaming/run_manager.py` (`RunState`, `RunManager` with 20-run / 6h cap, safe task wrapper, `resurrect_lead`, `dispatch_emails`).
6. Implement `backend/app/routers/pipeline_router.py` and mount it in `backend/app/main.py`.
7. Write `backend/tests/test_stage4_streaming.py` verifying:
   - Reconnecting with `last_event_id=10` replays exact events `11..N` without duplicates.
   - `GeminiAPIUnavailableError` inside background task emits `pipeline_error` and cleanly closes SSE stream.
   - `DualLanePacer.flush()` guarantees all 50 verdicts emit before `pipeline_completed`.
   - `resurrect_lead` updates `RunState` + `TelemetryAggregator` and appears immediately in `export?format=csv`.

### Stage 4 Exit Gate (Definition of Done)
- All Stage 4 unit tests pass (`pytest backend/tests/test_stage4_streaming.py`).
- `curl -N http://localhost:8000/api/pipeline/{run_id}/stream` streams clean `id:`, `event:`, `data:` SSE frames end-to-end.

---

# STAGE 5: FINALIZED IMPLEMENTATION SPECIFICATION — Frontend Foundation & State Machine
*(Follow step-by-step during implementation — zero guesswork required)*

## 5.1 Locked Stage 5 Architecture & Policy

| Component | Locked Design |
| :--- | :--- |
| **State Management** | **Zustand** store (`useLeadSlayerStore`) with O(1) normalized ID maps (`leadsById`, `verdictsById`, `emailsById`) so each of the 50 lead tiles subscribes only to its own slice (60 FPS, zero wasted renders) |
| **SSE Transport** | Native browser `EventSource` with `Last-Event-ID` auto-resume + `GET /api/pipeline/{run_id}/state` snapshot recovery fallback |
| **Backend Proxy** | `next.config.ts` `rewrites`: `/api/:path*` → `http://127.0.0.1:8000/api/:path*` (zero CORS friction on localhost or demo tunnels; ensure Next route proxy does not buffer SSE, or allow optional direct `NEXT_PUBLIC_SSE_ORIGIN` override if needed) |
| **Command Center Flow** | Single-page Mission Control canvas with auto-focusing phases + top clickable Phase Stepper (`Audit → ICP Lock → Swarm → Bloodbath → Sniper`) |
| **Authentic Safe Replay** | Discreet `?mode=replay` URL param (or `Ctrl+Shift+M` dev hotkey) + subtle `LIVE GEMINI` / `CACHED REPLAY` dot in header. Replays **authentic cached output captured from a real Gemini run** in Stage 7 (`data/replay_snapshot.json`) — **zero fake/handwritten AI verdicts anywhere in code** |

---

## 5.2 Stage 5 File Additions (`frontend/src/`)

```text
frontend/
├── next.config.ts                 # /api/* -> FastAPI rewrite proxy
└── src/
    ├── store/
    │   └── useLeadSlayerStore.ts  # Normalized Zustand FSM + selectors + resetDemo()
    ├── hooks/
    │   └── useLeadSlayerStream.ts # EventSource lifecycle, typed listeners, /state recovery
    ├── lib/
    │   ├── api.ts                 # Typed fetch wrappers (preset, csv, start, resurrect, dispatch, export)
    │   └── constants.ts           # Tactical color tokens, SlayingLevel UI config, phase metadata
    └── components/
        └── shell/
            ├── CommandCenterShell.tsx  # Dark-ops frame, top bar, Reset Demo button (#9), Replay indicator
            ├── PhaseStepper.tsx        # Clickable 5-step progress rail (peek back at Audit/ICPs anytime)
            └── ErrorAlertBanner.tsx    # Graceful GeminiAPIUnavailableError banner + 1-click Retry
```

---

## 5.3 Detailed Module Specifications

### A. `next.config.ts` — API Rewrite Proxy
* Configures `async rewrites()` mapping `/api/:path*` → `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/:path*`.
* *(Note on SSE through Next.js rewrites: Verify during Stage 5 integration that `EventSource('/api/pipeline/{id}/stream')` streams chunk-by-chunk without buffering in `next dev` / `next start`; if Next's dev proxy ever buffers SSE headers, `api.ts` supports an optional `NEXT_PUBLIC_STREAM_BASE_URL` fallback cleanly in 1 line.)*

### B. `src/store/useLeadSlayerStore.ts` — Normalized Zustand FSM
**State Shape:**
* `runId: string | null`
* `phase: PipelinePhase` (`"IDLE"`)
* `activeViewTab: "AUDIT" | "BLOODBATH" | "SNIPER"` (auto-advances with `phase`, manually clickable on `PhaseStepper`)
* `executionMode: ExecutionMode` (`"LIVE"`, flips to `"SAFE_REPLAY"` if `?mode=replay` is present in URL)
* `startupInput: StartupInput`
* `leadOrder: string[]` (ordered 50 `lead_id`s so grid order never jumps)
* `leadsById: Record<string, LeadRecord>`
* `marketAudit: MarketAuditResult | null`
* `icps: ICPProfile[]`
* `verdictsById: Record<string, SlayerVerdict>`
* `emailsById: Record<string, EmailDraft>`
* `telemetry: TelemetryMetrics | null`
* `selectedLeadId: string | null` (opens forensic autopsy drawer `#6`)
* `activeCategoryFilter: RejectionCategory | "ALL" | "SURVIVED"` (`"ALL"` default, `#6`)
* `agentLogs: string[]` (capped to last 40 lines)
* `errorMessage: string | null`

**Key Actions:**
* `setPresetData(startup, leads)` — populates `startupInput`, `leadOrder`, `leadsById`
* `setCustomLeads(leads)` — replaces `leadOrder` + `leadsById` after CSV upload
* `applyStreamEvent(event: StreamEvent)` — exhaustive `switch (event.event_type)` updating only the affected map key (`verdictsById[verdict.lead_id] = verdict`, etc.) + auto-advancing `activeViewTab` (`AUDITING` → `"AUDIT"`, `SLAYING` → `"BLOODBATH"`, `READY` → `"SNIPER"`)
* `hydrateFromSnapshot(snapshot: RunStateSnapshot)` — one-shot recovery from `GET /api/pipeline/{run_id}/state`
* `applyResurrection(verdict, emailDraft, telemetry)` — updates `verdictsById`, `emailsById`, and `telemetry` immediately (`#4`)
* `markDispatched(leadIds)` — flips `emailsById[id].status = "SENT"` and `phase = "DISPATCHED"`
* `resetDemo()` — cancels stream, resets `runId`, `phase = "IDLE"`, clears `verdictsById`, `emailsById`, `marketAudit`, `icps`, `telemetry`, `errorMessage` (`#9`)

### C. `src/hooks/useLeadSlayerStream.ts` — Bulletproof `EventSource` Hook
1. Subscribes whenever `runId` changes and `phase` is active (`!= "IDLE" | "READY" | "DISPATCHED" | "ERROR"`).
2. Opens `new EventSource(\`/api/pipeline/\${runId}/stream\`)`.
3. Registers typed listeners for all 10 `StreamEventType` names (`phase_changed`, `agent_log`, `audit_completed`, `icps_generated`, `leads_loaded`, `lead_verdict`, `email_drafted`, `telemetry_update`, `pipeline_completed`, `pipeline_error`).
4. Tracks `lastEventIdRef` on every incoming event.
5. **Clean Termination:** On `pipeline_completed` or `pipeline_error`, closes `EventSource` immediately so the browser doesn't endlessly reconnect to a finished stream.
6. **Self-Healing Fallback:** On `onerror`, if `EventSource` drops unexpectedly twice, fetches `GET /api/pipeline/${runId}/state` and calls `hydrateFromSnapshot()` so the UI never gets stuck!

### D. `src/lib/api.ts` — Typed API Client
Clean async helpers using typed JSON & `FormData`:
* `fetchHealth()`, `fetchDemoPreset()`, `parseCsvLeads(file)`
* `startPipeline(input: StartupInput) -> { run_id, stream_url }`
* `fetchRunState(runId) -> RunStateSnapshot`
* `resurrectLead(runId, leadId) -> { verdict, email_draft, telemetry }`
* `dispatchEmails(runId, leadIds) -> { dispatched_count, sent_at }`
* `getExportUrl(runId, format: "csv" | "json") -> string`

### E. `src/components/shell/` — Tactical Layout Frame
* **`CommandCenterShell.tsx`:** Deep obsidian (`#07090D`) background, crisp 1px zinc borders, top HUD bar with LeadSlayer logo, discreet `LIVE GEMINI` / `CACHED REPLAY` status pill, **Reset Demo** button (`#9`), and `PhaseStepper`.
* **`PhaseStepper.tsx`:** 5 visual steps (`Market Audit` → `ICP & Memory` → `Hunter Swarm` → `The Bloodbath` → `Sniper Deck`), highlighting active/completed states and letting the presenter jump views (`AUDIT` / `BLOODBATH` / `SNIPER`) cleanly.
* **`ErrorAlertBanner.tsx`:** Renders `GeminiAPIUnavailableError` messages prominently in amber/crimson with a **Retry Run** button.

---

## 5.4 Stage 5 Step-by-Step Implementation Checklist

1. Install `zustand` inside `/frontend`.
2. Update `frontend/next.config.ts` with `/api/:path*` rewrite proxy.
3. Verify `frontend/src/types/contracts.ts` includes `RunStateSnapshot`, `StreamEvent` discriminated union, and `ExecutionMode`.
4. Implement `frontend/src/lib/api.ts` and `frontend/src/lib/constants.ts`.
5. Implement `frontend/src/store/useLeadSlayerStore.ts` with O(1) maps + `resetDemo()`.
6. Implement `frontend/src/hooks/useLeadSlayerStream.ts` (`EventSource` + `Last-Event-ID` + `/state` fallback + `?mode=replay` detector).
7. Implement `CommandCenterShell.tsx`, `PhaseStepper.tsx`, and `ErrorAlertBanner.tsx`, and mount into `frontend/src/app/page.tsx`.
8. Run `npx tsc --noEmit` and `npm run build` to confirm zero TypeScript or Next.js build errors, and verify live SSE connection against running FastAPI `/api/pipeline/{run_id}/stream`.

### Stage 5 Exit Gate (Definition of Done)
- `npx tsc --noEmit` and `npm run build` pass with zero errors.
- Triggering a run from the Stage 5 shell streams live `StreamEvent`s into Zustand and advances `PhaseStepper` automatically without console warnings or orphaned `EventSource` sockets.

---

# STAGE 6: FINALIZED IMPLEMENTATION SPECIFICATION — Kinetic "Bloodbath" UI & Sniper Command Deck
*(Follow step-by-step during implementation — zero guesswork required)*

## 6.1 Locked Stage 6 Architecture & Visual Policy

| Component | Locked Design |
| :--- | :--- |
| **50-Lead Layout** | Compact **50-Tile Tactical Matrix Grid** (`grid-cols-2 md:grid-cols-5 xl:grid-cols-10` or `5×10` responsive density) fitting on a single 1080p projector screen |
| **Kill Visuals** | Crimson flash + diagonal animated strike-through slash + punchy `headline_tag` badge + slight dim (`opacity-55`) so green survivors pop — **stays clickable** |
| **Phase Transition** | Holds `2.0s` after final verdict to showcase the `42 Killed / 8 Survived` grid, then auto-glides into **Sniper Command Deck** when emails finish (PhaseStepper lets user flip back anytime) |
| **Proof Traceability (`#1`)** | Inline emerald highlight on `email_evidence_phrase` inside each email body + hover/click **Proof Popover** showing `cited_survival_signal`, `matched_product_chunk`, and `icp_similarity_score` |
| **Audio Policy** | Pure 60 FPS GPU-accelerated visuals (`transform`, `opacity`, CSS borders) — **zero browser audio** |

---

## 6.2 Stage 6 File Additions (`frontend/src/components/`)

```text
frontend/src/components/
├── audit/
│   ├── AuditWorkspace.tsx         # Act 1 container: Startup input, CSV/Preset loader, launch CTA
│   ├── SlayingLevelSelector.tsx   # Tactical 3-pill switch: Scout (Amber) / Tactical (Orange) / Bloodbath (Crimson) (#5)
│   ├── MarketAuditCard.tsx        # Market reality summary, readiness score, founder blind spots
│   ├── ICPCardsGrid.tsx           # 3 glowing ICP cards with target roles, stack signals & triggers
│   └── AntiICPLockStrip.tsx       # Animated "Anti-ICP Kill Rules Locked Into Slayer" banner (#3)
├── bloodbath/
│   ├── BloodbathMatrix.tsx        # 50-tile matrix container + live filter logic + auto-advance timer
│   ├── LeadTile.tsx               # React.memo tile subscribing ONLY to verdictsById[leadId] (60 FPS)
│   ├── SlayerAutopsyBar.tsx       # Live Kill/Survive HUD counters + clickable category filter pills (#6)
│   └── LeadAutopsyDrawer.tsx      # Slide-over inspector: full lead data, scores, reasoning + Resurrect button (#4)
└── sniper/
    ├── SniperDeck.tsx             # Act 3 container: surviving & resurrected green email cards grid
    ├── SniperEmailCard.tsx        # Subject, editable/toggleable approve checkbox, match % badge
    ├── EvidenceHighlightedBody.tsx # Splits email body around email_evidence_phrase + Proof Popover (#1)
    └── DispatchExportBar.tsx      # Bottom sticky bar: Export CSV, Export Kill Audit JSON (#10), Approve All & Send
```

---

## 6.3 Detailed Component Specifications

### A. Act 1 — `audit/` Components
1. **`AuditWorkspace.tsx`:**
   * Top-right button: **"Load KubeGuard AI + 50-Lead Swarm"** (calls `fetchDemoPreset()`, populates store in 1 click).
   * Drag-and-drop / file-picker CSV box calling `parseCsvLeads(file)` with instant badge `"50 Leads Loaded & Validated"`.
   * **`SlayingLevelSelector.tsx` (`#5`):** 3 high-contrast tactile buttons:
     * `LENIENT` (**Scout** — Amber `#F59E0B`): *"Kills hard blockers only"*
     * `NORMAL` (**Tactical** — Orange `#F97316`): *"Balanced ICP & stack triage"*
     * `RUTHLESS` (**Bloodbath** — Crimson `#EF4444`, default): *"Zero mercy (~85% kill rate)"*
   * Primary CTA: **"Launch Autonomous GTM Engine"** (triggers `startPipeline(startupInput)`).
2. **`MarketAuditCard.tsx` + `ICPCardsGrid.tsx` + `AntiICPLockStrip.tsx` (`#3`):**
   * `MarketAuditCard.tsx` shows the **Readiness Breakdown** (`pain_urgency`, `icp_clarity`, `differentiation`, `timing_fit`), badges for `Live Site Read` / `Search Grounded`, the **Assumption vs. Reality Gap Analysis Table** (`assumption_gaps`), and **Competitor Wedge** cards (`competitor_landscape`).
   * Uses Framer Motion `staggerChildren: 0.08` to reveal the 3 ICP cards smoothly.
   * `AntiICPLockStrip.tsx` animates a crisp shield/lock icon snapping `marketAudit.anti_icp_red_flags` into the Slayer pipeline before Act 2 activates.

### B. Act 2 — `bloodbath/` Components (The 60 FPS Centerpiece)
1. **`SlayerAutopsyBar.tsx` (`#6`):**
   * Displays a compact **Hunter Signals & Queries Strip** (`hunterReport.hunt_queries`) showing the exact Boolean hunt queries & sources generated from the ICPs.
   * Large tabular numerals: `PROCESSED: X/50`, `KILLED: 42` (crimson), `SURVIVED: 8` (emerald), `KILL RATE: 84%`.
   * Horizontal clickable filter pills bound to `activeCategoryFilter`:
     `ALL (50)` | `SURVIVED (8)` | `COMPETITOR_LOCK_IN` | `TOO_SMALL` | `LAYOFFS_FREEZE` | `WRONG_PERSONA` | `NO_STACK_FIT` | `NO_URGENCY_SIGNAL`.
2. **`LeadTile.tsx` (Strict `React.memo` + Single-Key Zustand Selector):**
   * Subscribes via `const verdict = useLeadSlayerStore(s => s.verdictsById[leadId])`.
   * **3 Visual States (GPU-only `transform` + `opacity`):**
     * `PENDING`: subtle slate border (`border-zinc-800`), gentle pulse dot (`Scanning...`).
     * `KILLED`: brief crimson flash (`initial={{ scale: 1.04 }} animate={{ scale: 1 }}`), animated diagonal CSS/SVG red strike-through line (`scaleX: 0 -> 1` in `0.22s`), `opacity-60`, crisp red pill (`headline_tag`), and muted score badge (`score: 28`).
     * `SURVIVED`: emerald glow border (`border-emerald-500/80`), subtle pop (`scale: [1, 1.05, 1]`), green pill (`headline_tag`), and bright `qualification_score` badge (`94/100`).
   * Dimmed/non-matching tiles when `activeCategoryFilter !== "ALL"` drop to `opacity-20` so matching category leads leap off the screen!
3. **`LeadAutopsyDrawer.tsx` (`#4` + `#6`):**
   * Opens when clicking any `LeadTile`.
   * Displays full lead profile (`role`, `company`, `employee_count`, `funding_stage`, `tech_stack`, `recent_signal`).
   * Displays mathematical transparency bars: **ICP Vector Match %**, **Structural Fit %**, **Anti-ICP Risk %**, and final **Qualification Score (`0–100`)**.
   * Shows Slayer's `reasoning` verbatim.
   * If `verdict.survived === false`: renders **"Resurrect Lead & Draft Email"** button → shows loading spinner → calls `POST /api/pipeline/{run_id}/resurrect/{lead_id}` → calls `applyResurrection()` so the tile flips emerald green immediately!

### C. Act 3 — `sniper/` Components
1. **`SniperDeck.tsx`:**
   * Renders all leads where `verdictsById[id]?.survived === true` (including resurrected ones, tagged `"RESURRECTED"` in amber-emerald!).
   * Responsive 2-column grid of `SniperEmailCard`s with Framer Motion staggered entrance.
2. **`EvidenceHighlightedBody.tsx` (`#1`):**
   * Case-insensitively splits `draft.body` at `draft.email_evidence_phrase`.
   * Wraps the matched phrase in `<mark className="bg-emerald-500/20 text-emerald-300 border-b border-emerald-400 cursor-pointer px-1 rounded">`.
   * Clicking or hovering the `<mark>` opens a sleek floating **Evidence Proof Card** displaying:
     1. **Lead Buying Signal:** `draft.cited_survival_signal`
     2. **Stage 2 Product Match:** `draft.matched_product_chunk`
     3. **ICP Vector Fit:** `${Math.round(verdict.icp_similarity_score * 100)}%`
3. **`DispatchExportBar.tsx` (`#10`):**
   * Sticky bottom command bar showing `X of Y Survivor Emails Approved`.
   * Secondary buttons: **"Export Survivors (.CSV)"** and **"Export Kill Audit (.JSON)"** (triggering `/api/pipeline/{run_id}/export?format=...`).
   * Primary massive CTA: **"Approve All & Send (N Emails)"** → calls `dispatchEmails()` → transitions badges to `SENT` with a crisp emerald confirmation banner.

---

## 6.4 Stage 6 Step-by-Step Implementation Checklist

1. Build Act 1 components (`AuditWorkspace`, `SlayingLevelSelector`, `MarketAuditCard`, `ICPCardsGrid`, `AntiICPLockStrip`).
2. Build Act 2 components (`SlayerAutopsyBar`, `LeadTile` with `React.memo`, `BloodbathMatrix`, `LeadAutopsyDrawer` with Resurrect action).
3. Build Act 3 components (`EvidenceHighlightedBody`, `SniperEmailCard`, `SniperDeck`, `DispatchExportBar`).
4. Wire all 3 Acts cleanly inside `frontend/src/app/page.tsx` driven by `activeViewTab` and `phase`.
5. Run `npx tsc --noEmit`, `npm run build`, and visually verify 60 FPS Bloodbath performance + mobile/projector responsiveness at `1280×720` and `1920×1080`.

### Stage 6 Exit Gate (Definition of Done)
- All 50 tiles fit cleanly on a `1920×1080` screen without horizontal overflow and animate smoothly at 60 FPS.
- Clicking any killed tile opens `LeadAutopsyDrawer` and **Resurrect** flips the tile green + creates a `SniperEmailCard`.
- Hovering/clicking the highlighted phrase inside a Sniper email opens the Evidence Proof Card.
- Export `.CSV` and `.JSON` buttons download valid files reflecting live/resurrected state.

---

# STAGE 7: FINALIZED IMPLEMENTATION SPECIFICATION — Integration, Authentic Replay Capture & Stage Choreography
*(Follow step-by-step during implementation — zero guesswork required)*

## 7.1 Locked Stage 7 Architecture & Policy

| Component | Locked Design |
| :--- | :--- |
| **Replay Capture (`5A`)** | `backend/app/scripts/record_replay_snapshot.py` runs the **actual live ADK + Gemini pipeline** once and persists the authentic captured output (`data/replay_snapshot.json`) — zero fabricated/handwritten AI responses |
| **One-Command Launcher** | Root `start_demo.sh` validates `.env` (`GEMINI_API_KEY`), starts FastAPI (`:8000`) + Next.js (`:3000`), verifies `/api/health`, and traps `SIGINT`/`SIGTERM` cleanly |
| **Pre-Pitch Warmup** | Run 1 live warmup 10 minutes before pitch so `gemini-embedding-2` vectors sit fresh inside the 6h cache while `Hydrogen` & `Flash-Lite` run 100% live on stage |
| **E2E Verification** | `backend/tests/test_e2e_pipeline.py` (fast mocked CI default + `--live` real-Gemini calibration mode) |

---

## 7.2 Stage 7 File Additions

```text
Agent/
├── start_demo.sh                                  # Single-command launcher (Backend + Frontend + health gate)
├── backend/
│   ├── app/scripts/record_replay_snapshot.py      # Captures 1 real live Gemini run -> data/replay_snapshot.json
│   └── tests/test_e2e_pipeline.py                 # Full E2E test (start -> stream -> resurrect -> dispatch -> export)
└── data/
    └── replay_snapshot.json                       # Populated ONLY by record_replay_snapshot.py from real Gemini output
```

---

## 7.3 Detailed Module & Operations Specifications

### A. `record_replay_snapshot.py` — Authentic Real-Gemini Capture
* **Purpose:** Ensures `?mode=replay` (used strictly if conference Wi-Fi dies) replays a **100% genuine, unedited Gemini run** captured directly from our live ADK pipeline.
* **Execution:**
  1. Loads `data/default_startup.json` + `data/leads_50.json`.
  2. Executes `PipelineOrchestrator` with `execution_mode="LIVE"` in `RUTHLESS` mode.
  3. Asserts run completed without error (`phase == "READY"`), `len(verdicts) == 50`, and `4 <= survived_count <= 12`.
  4. Serializes `{ "captured_at": iso_utc, "source": "live_gemini_adk_run", "models": [...], "startup": ..., "snapshot": RunStateSnapshot, "events": list[StreamEvent] }` atomically to `data/replay_snapshot.json`.
* **Replay Fidelity:** When `ExecutionMode.SAFE_REPLAY` is triggered, `PipelineOrchestrator` streams those exact recorded `StreamEvent`s through `DualLanePacer` (`~90ms` Bloodbath cascade) and hydrates `RunState` so `Resurrect` (cached/live), `Dispatch`, and `Export` continue working seamlessly.

### B. `start_demo.sh` — Bulletproof Single-Terminal Boot
1. Checks `.env` exists and `GEMINI_API_KEY` is non-empty (fails fast with clear message if missing).
2. Starts FastAPI (`uvicorn app.main:app --host 127.0.0.1 --port 8000`) inside `/backend/.venv` in background.
3. Polls `http://127.0.0.1:8000/api/health` (max 15s) until `{"status": "ok"}`.
4. Starts Next.js (`npm run start` after build, or `npm run dev` during iteration) inside `/frontend` on `:3000`.
5. Prints clean banner:
   * `Command Center UI:  http://localhost:3000`
   * `Emergency Replay:   http://localhost:3000/?mode=replay`
   * `Backend API Docs:   http://localhost:8000/docs`
6. Uses `trap 'kill $BACK_PID $FRONT_PID 2>/dev/null' EXIT INT TERM` so `Ctrl+C` leaves zero zombie processes on ports `8000` or `3000`.

### C. `test_e2e_pipeline.py` — Integration & Calibration Gate
* **Default Fast Mode (`pytest backend/tests/test_e2e_pipeline.py`):**
  * Exercises full HTTP/SSE lifecycle via `httpx.AsyncClient` + FastAPI `TestClient` (with deterministic mocked Gemini responses):
    1. `GET /api/demo/preset` → 50 leads.
    2. `POST /api/pipeline/start` → `run_id`.
    3. `GET /api/pipeline/{run_id}/stream` → verifies monotonic `event_id`s, `audit_completed`, `icps_generated`, 50 `lead_verdict`s, survivor `email_drafted`s, and `pipeline_completed`.
    4. `POST /api/pipeline/{run_id}/resurrect/{killed_lead_id}` → confirms flip to `survived=True, resurrected_by_user=True` + telemetry update.
    5. `POST /api/pipeline/{run_id}/dispatch` → confirms `SENT` status.
    6. `GET /api/pipeline/{run_id}/export?format=csv` & `format=json` → confirms resurrected lead appears in Survivors CSV and full 50-lead audit appears in JSON.
* **Live Calibration Mode (`pytest backend/tests/test_e2e_pipeline.py --live`):**
  * Runs live Gemini calls on `data/leads_50.json` in `RUTHLESS` vs `LENIENT` and verifies:
    * `RUTHLESS` kill rate sits in **`76%–90%`** (~38–45 killed, ~5–12 survived).
    * `LENIENT` produces strictly more survivors than `RUTHLESS` (proving the 5 borderline leads respond to Slaying Level).
    * Every Sniper `EmailDraft.email_evidence_phrase` exists inside `EmailDraft.body`.

### D. Chaos & Proxy Verification Checklist
1. **SSE Unbuffered Check:** Verify `EventSource('/api/pipeline/{id}/stream')` delivers `lead_verdict` events one-by-one in real time through Next.js `:3000` (if Next.js `rewrites` ever buffers chunked SSE, switch `stream_url` in `useLeadSlayerStream` to `NEXT_PUBLIC_SSE_ORIGIN` `http://127.0.0.1:8000` with FastAPI CORS enabled).
2. **Custom CSV Check:** Upload a tweaked CSV with capitalized headers (`Company`, `Role`, `Employee Count`) and verify clean parsing + Bloodbath run.
3. **Rate-Limit Error Check:** Temporarily simulate a `429` in test and verify `ErrorAlertBanner` shows *"Gemini API limit reached or service is temporarily overloaded..."* cleanly.

---

## 7.4 The 3-Minute Live Stage Choreography (180-Second Playbook)

| Time | Stage Act & Clicks | What Judges See & Hear |
| :--- | :--- | :--- |
| **0:00 – 0:30** | **Hook & Setup** *(Act 1)* | *"Every AI sales tool today blasts 1,000 spam emails and ruins your domain. LeadSlayer flips this: our primary agent doesn't look for reasons to email you—it hunts for reasons to KILL the lead."* Click **"Load KubeGuard AI + 50-Lead Swarm"**, point to **Bloodbath (Ruthless)** mode, hit **Launch**. |
| **0:30 – 1:05** | **Audit & ICP Lock-In** *(Step 1 → Step 2)* | **`gemini-4-hydrogen`** audits the naive founder pitch, exposes blind spots, and **`gemini-embedding-2`** locks in **3 ICP cards** + snaps **Anti-ICP Kill Rules** directly into the Slayer. |
| **1:05 – 1:55** | **The Bloodbath** *(Step 3 → Step 4)* | Matrix opens across all 50 leads. **`gemini-3.5-flash-lite`** tears through them at ~90ms cascade: ~42 tiles slash red (`KILLED: Datadog Lock-In`, `KILLED: Layoffs Freeze`, `KILLED: Too Small`) while ~8 glow emerald green. Click **1 killed tile** to show the Forensic Autopsy + optional **Resurrect Lead** human override. |
| **1:55 – 2:35** | **The Sniper Deck** *(Step 5)* | Auto-transitions to the 8 surviving green emails drafted by **`gemini-4-hydrogen`** using Stage 2 vector retrieval. Hover the glowing emerald phrase inside an email to show the **Evidence Proof Card** (`Lead Signal` + `Matched Product Feature` + `94% ICP Match`). |
| **2:35 – 3:00** | **Action & Close** | Click **"Export Survivors (.CSV)"** (showing HubSpot/Instantly readiness) and hit **"Approve All & Send (8 Emails)"**. *"42 bad emails never left the building. 8 high-conviction conversations just started. That's LeadSlayer AI."* |

---

## 7.5 Pre-Pitch 10-Minute Checklist
1. Run `./start_demo.sh` and confirm `LIVE GEMINI` green dot at `http://localhost:3000`.
2. Run 1 full warmup pass on `KubeGuard AI` (verifies internet/API key + refreshes the 6-hour `gemini-embedding-2` cache).
3. Click **Reset Demo** so the screen sits clean on Act 1 ready for `0:00`.
4. Keep `http://localhost:3000/?mode=replay` bookmarked in a second tab **only** as an emergency Wi-Fi parachute.

---

## 7.6 Stage 7 Step-by-Step Implementation Checklist

1. Implement `backend/app/scripts/record_replay_snapshot.py` and run it once against live Gemini to generate `data/replay_snapshot.json`.
2. Verify `ExecutionMode.SAFE_REPLAY` in `PipelineOrchestrator` streams directly from `data/replay_snapshot.json` via `DualLanePacer`.
3. Create root `start_demo.sh` (`chmod +x start_demo.sh`) with `.env` check, health poll, and clean trap teardown.
4. Implement `backend/tests/test_e2e_pipeline.py` (mocked default + `--live` calibration mode).
5. Run live calibration pass (`--live`) across `RUTHLESS` and `LENIENT`; fine-tune `prompts.py` or borderline lead signals in `data/leads_50.json` if needed so `RUTHLESS` hits ~40–44 kills reliably.
6. Run full test suite (`pytest`) + frontend build (`npm run build`) + 1 rehearsal run via `./start_demo.sh`.

### Final Project Exit Gate (100% Demo-Ready)
- `pytest` (Stages 1, 2, 3, 4 + E2E) passes 100%.
- `npx tsc --noEmit && npm run build` passes with zero errors.
- `./start_demo.sh` boots cleanly in `< 10 seconds` and executes a full 3-minute rehearsed demo end-to-end without warnings or hiccups.
