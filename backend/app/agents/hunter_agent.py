from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from google import genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.rate_limiter import GentleAdaptiveExecutor, key_rotator
from app.agents.structured_outputs import (
    DiscoveredLeadBatch,
    DiscoveredLeadCandidate,
    EnrichedLeadBatch,
    HuntQueriesOutput,
    WebSearchQueriesOutput,
)
from app.config import settings
from app.harvey_bridge.research import (
    HarveyCompanyDossier,
    is_junk_or_self_domain,
    research_company_with_harvey,
    search_linkedin_via_harvey_browser,
)
from app.harvey_bridge.web_index import has_live_web_index, query_live_web_index
from app.memory.exceptions import is_transient_api_error
from app.memory.registry import memory_registry
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    HunterReport,
    HuntQuery,
    ICPProfile,
    LeadRecord,
    ModelId,
    PipelinePhase,
    StartupInput,
)
from app.services.url_fetcher import fetch_site_context


def _normalize_root_domain(raw_domain_or_url: str | None) -> str:
    if not raw_domain_or_url:
        return ""
    candidate = raw_domain_or_url.strip().lower()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlparse(candidate).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _is_directory_or_self_domain(domain: str, own_domain: str) -> bool:
    return is_junk_or_self_domain(domain, own_domain)


def _new_genai_client(api_key: str) -> genai.Client:
    return genai.Client(
        api_key=api_key,
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )


async def _synthesize_live_web_queries(
    startup: StartupInput,
    icps: list[ICPProfile],
    mode: str,
    desired_queries: int,
    client: Any | None = None,
) -> list[str]:
    """Generates clean, high-signal web or LinkedIn X-Ray search strings for our web index."""
    icp_summary = "\n".join(
        f"- {icp.name}: roles={icp.target_roles[:4]}, tech={icp.required_tech_signals[:4]}, triggers={icp.buying_triggers[:3]}"
        for icp in icps
    )
    if mode == "LINKEDIN":
        sys_msg = (
            f"Generate {desired_queries} Google X-Ray search queries targeting `site:linkedin.com/in/` "
            "for real B2B decision-makers matching the ICPs. Each query MUST start with `site:linkedin.com/in/` "
            "and combine target job titles with relevant industry/tech keywords."
        )
    else:
        sys_msg = (
            f"Generate {desired_queries} crisp Google search queries to discover real mid-market operating B2B/B2C companies "
            "(20-300 employees) matching the ICPs and buying signals. Append `-site:linkedin.com -site:crunchbase.com -site:g2.com -site:wikipedia.org` "
            "so results point to company websites, announcements, press releases, or engineering blogs."
        )

    attempts = max(2, key_rotator.pool_size) if client is None else 1
    for _ in range(attempts):
        active_key = ""
        if client is None:
            active_key = key_rotator.next_key()
            genai_client = _new_genai_client(active_key)
        else:
            genai_client = client
        try:
            resp = await genai_client.aio.models.generate_content(
                model=settings.gemini_workhorse_model,
                contents=(
                    f"Product: {startup.product_name} ({startup.product_url or 'N/A'})\n"
                    f"Description: {startup.description}\n"
                    f"Target ICPs:\n{icp_summary}"
                ),
                config=genai.types.GenerateContentConfig(
                    system_instruction=sys_msg,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=WebSearchQueriesOutput,
                ),
            )
            if client is None and active_key:
                key_rotator.mark_ok(active_key)
            parsed = WebSearchQueriesOutput.model_validate_json(resp.text or "{}")
            clean = [q.strip() for q in parsed.queries if q and q.strip()]
            if clean:
                return clean[:desired_queries]
        except Exception as exc:
            if client is None and active_key and ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)):
                key_rotator.mark_throttled(active_key)
            continue

    # Deterministic fallback queries if synthesis fails
    first_icp = icps[0] if icps else None
    roles = " OR ".join(f'"{r}"' for r in (first_icp.target_roles[:2] if first_icp else ["VP Engineering"]))
    tech = " OR ".join(f'"{t}"' for t in (first_icp.required_tech_signals[:2] if first_icp else ["SaaS"]))
    if mode == "LINKEDIN":
        return [f"site:linkedin.com/in/ ({roles}) ({tech})"]
    return [f'({tech}) ({startup.product_name} OR B2B SaaS) hiring OR expansion -site:linkedin.com -site:crunchbase.com']


async def _run_discovery_search(
    prompt: str,
    *,
    startup: StartupInput | None = None,
    icps: list[ICPProfile] | None = None,
    mode: str = "AI",
    target_count: int = 15,
    callbacks: PipelineCallbacks | None = None,
    client: Any | None = None,
) -> tuple[str, list[str], bool]:
    """
    Runs live web discovery: prefers our encapsulated live web index when configured
    (saving Gemini Search quota cleanly), and falls back to grounded/inference Gemini search.
    """
    if client is None and startup is not None and icps and has_live_web_index():
        query_count = 4 if target_count > 20 else 2
        pages = 2 if target_count > 20 else 1
        queries = await _synthesize_live_web_queries(
            startup, icps, mode=mode, desired_queries=query_count, client=None
        )
        if callbacks is not None:
            await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
        notes, urls = await query_live_web_index(
            queries, num_per_query=10, pages_per_query=pages
        )
        if notes and urls:
            return notes, urls, True

    return await _run_grounded_gemini_search(prompt, client=client)


async def _run_grounded_gemini_search(
    prompt: str,
    client: Any | None = None,
) -> tuple[str, list[str], bool]:
    if client is not None:
        res = await client.aio.models.generate_content(
            model=settings.gemini_workhorse_model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.2),
        )
        text = (res.text or "").strip()
        if not text:
            raise RuntimeError("Search discovery returned empty results.")
        return text, [], False

    last_exc: Exception | None = None

    # 1. Try Google Search grounding ONLY on keys whose search quota is unblocked,
    # quarantining search separately so 404/429 never blocks healthy inference keys.
    search_models = ["gemini-2.5-flash", "gemini-3.8-flash", settings.gemini_brain_model]
    for _ in range(min(2, key_rotator.pool_size)):
        search_key = key_rotator.next_search_key()
        if not search_key:
            break
        s_client = _new_genai_client(search_key)
        hit_search_limit = False
        for model_name in search_models:
            try:
                res = await s_client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())],
                        temperature=0.2,
                    ),
                )
                text = (res.text or "").strip()
                if not text:
                    continue
                grounding_urls: list[str] = []
                cand = res.candidates[0] if getattr(res, "candidates", None) else None
                gm = getattr(cand, "grounding_metadata", None)
                chunks = getattr(gm, "grounding_chunks", None) or []
                for ch in chunks:
                    uri = getattr(getattr(ch, "web", None), "uri", None)
                    if uri:
                        grounding_urls.append(uri)
                key_rotator.mark_search_ok(search_key)
                return text, grounding_urls, True
            except Exception as exc:
                last_exc = exc
                err_s = str(exc)
                if "429" in err_s or "RESOURCE_EXHAUSTED" in err_s or "404" in err_s:
                    hit_search_limit = True
                    continue
                break
        if hit_search_limit:
            key_rotator.mark_search_throttled(search_key)

    # 2. Fallback to standard non-search inference rotated across healthy keys
    for _ in range(max(2, key_rotator.pool_size)):
        infer_key = key_rotator.next_key()
        i_client = _new_genai_client(infer_key)
        try:
            res = await i_client.aio.models.generate_content(
                model=settings.gemini_workhorse_model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(temperature=0.2),
            )
            text = (res.text or "").strip()
            if text:
                key_rotator.mark_ok(infer_key)
                return text, [], False
        except Exception as exc:
            last_exc = exc
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                key_rotator.mark_throttled(infer_key)
                continue
            if is_transient_api_error(exc):
                raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Search discovery returned empty results.")


async def _extract_structured_candidates(
    raw_notes: str,
    grounding_urls: list[str],
    target_n: int,
    callbacks: PipelineCallbacks,
    used_live_search: bool = True,
    client: Any | None = None,
) -> list[DiscoveredLeadCandidate]:
    name_rule = (
        "- CRITICAL: Copy a human `full_name` and `linkedin_url` ONLY if explicitly observed in NOTES/URLS; "
        "NEVER invent or guess fictional person names — use role labels like `Brand & Packaging Team` or `Operations Leadership` when unverified."
        if used_live_search
        else "- CRITICAL: Live web search fell back to cached knowledge for this pass; set `full_name` to a department/role label like `Operations Leadership` or `Brand & Packaging Team` (and leave `linkedin_url` empty) so live website HTML extraction resolves real owners safely."
    )
    extract_prompt = (
        f"Convert these prospect discovery notes into up to {target_n} unique structured B2B lead candidates.\n"
        f"Rules:\n"
        f"- `domain` MUST be a clean root company domain like `rhodeskin.com` (not `linkedin.com`, no `https://`).\n"
        f"{name_rule}\n"
        f"- Preserve concrete signals, dates, and company facts.\n\n"
        f"NOTES:\n{raw_notes}\n\n"
        f"GROUNDING URLS:\n" + "\n".join(grounding_urls[:60])
    )

    async def _extract(_: int) -> DiscoveredLeadBatch:
        active_key = ""
        if client is None:
            active_key = key_rotator.next_key()
            genai_client = _new_genai_client(active_key)
        else:
            genai_client = client
        try:
            resp = await genai_client.aio.models.generate_content(
                model=settings.gemini_workhorse_model,
                contents=extract_prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=DiscoveredLeadBatch,
                ),
            )
            if client is None and active_key:
                key_rotator.mark_ok(active_key)
            return DiscoveredLeadBatch.model_validate_json(resp.text or "{}")
        except Exception as exc:
            if client is None and active_key and ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)):
                key_rotator.mark_throttled(active_key)
            raise

    executor = GentleAdaptiveExecutor(
        concurrency=1, launch_stagger_s=0.0, max_retries=max(2, key_rotator.pool_size)
    )
    async for _, batch in executor.run_stream([0], _extract):
        await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
        return batch.candidates
    return []


async def _search_ai_candidates(
    startup: StartupInput,
    icps: list[ICPProfile],
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> tuple[list[DiscoveredLeadCandidate], list[str]]:
    desired_qualified = getattr(startup, "target_qualified_leads", 10) or 10
    multiplier = 2.0 if startup.slaying_level.value == "RUTHLESS" else 1.5
    target_needed = max(startup.target_lead_count, min(75, int(desired_qualified * multiplier)))

    await callbacks.on_log(
        f"[HunterSwarm · AI Search] Hunting live web companies matching {startup.product_name} ICPs (target: {target_needed} candidates)..."
    )

    # If target_needed > 25 and multiple ICPs exist, shard across ICPs for deep market coverage
    if target_needed > 25 and len(icps) >= 2:
        per_icp_target = max(10, min(25, int(target_needed / len(icps)) + 2))
        all_cands: list[DiscoveredLeadCandidate] = []
        all_srcs: list[str] = []

        for idx, icp in enumerate(icps, start=1):
            icp_single_text = (
                f"- {icp.id} ({icp.name}): roles={icp.target_roles}, size={icp.min_employees}-{icp.max_employees}, "
                f"signals={icp.required_tech_signals}, triggers={icp.buying_triggers}"
            )
            prompt = (
                f"Search the live web and find {per_icp_target} REAL operating companies (with exact official domains) for:\n"
                f"Seller Product: {startup.product_name} ({startup.product_url or 'N/A'})\n"
                f"Description: {startup.description}\n\n"
                f"Specific ICP Angle {idx}/{len(icps)}: {icp.name}\n{icp_single_text}\n\n"
                f"Requirements:\n"
                f"1. Target mid-market/growth companies (20-300 employees) matching this specific ICP with verifiable commercial signals.\n"
                f"2. Exclude {_normalize_root_domain(startup.product_url) or startup.product_name} and directory/social sites.\n"
                f"3. Include company name, official domain, likely buyer role, any real public executive name, industry, headcount, stage, and concrete signal."
            )
            try:
                notes, urls, used_search = await _run_discovery_search(
                    prompt,
                    startup=startup,
                    icps=[icp],
                    mode="AI",
                    target_count=per_icp_target,
                    callbacks=callbacks,
                    client=client,
                )
                await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
                cands = await _extract_structured_candidates(
                    notes, urls, per_icp_target, callbacks, used_live_search=used_search, client=client
                )
                all_cands.extend(cands)
                all_srcs.append("AI Google Search" if used_search else "AI Candidate Search")
            except Exception as e:
                await callbacks.on_log(f"[HunterSwarm · AI Search] Shard for {icp.name} note: {e}")
                continue

        if all_cands:
            await callbacks.on_log(
                f"[HunterSwarm · AI Search] Sharded hunt yielded {len(all_cands)} company candidates across {len(icps)} ICPs."
            )
            return all_cands, list(dict.fromkeys(all_srcs))

    # Single-pass search for standard volumes
    icp_text = "\n".join(
        f"- {icp.id} ({icp.name}): roles={icp.target_roles}, size={icp.min_employees}-{icp.max_employees}, "
        f"signals={icp.required_tech_signals}, triggers={icp.buying_triggers}"
        for icp in icps
    )
    target_n = min(target_needed, 30)
    prompt = (
        f"Search the live web and find {target_n} REAL operating companies (with exact official domains) for:\n"
        f"Seller Product: {startup.product_name} ({startup.product_url or 'N/A'})\n"
        f"Description: {startup.description}\n\n"
        f"Target ICPs:\n{icp_text}\n\n"
        f"Requirements:\n"
        f"1. Prioritize ~{max(4, int(target_n * 0.75))} mid-market/growth companies (20-250 employees, NOT giant public conglomerates) with verifiable 2025-2026 commercial buying events (SKU launches, retail rollouts, funding rounds, expansion, hiring) plus ~{max(2, target_n - max(4, int(target_n * 0.75)))} realistic misfits for filtering.\n"
        f"2. Exclude { _normalize_root_domain(startup.product_url) or startup.product_name } and directory/social sites.\n"
        f"3. Include company name, official domain, likely buyer role, any real public executive name, industry, headcount, stage, and concrete signal."
    )
    notes, urls, used_search = await _run_discovery_search(
        prompt,
        startup=startup,
        icps=icps,
        mode="AI",
        target_count=target_n,
        callbacks=callbacks,
        client=client,
    )
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    cands = await _extract_structured_candidates(
        notes, urls, target_n, callbacks, used_live_search=used_search, client=client
    )
    src = ["AI Google Search" if used_search else "AI Candidate Search"]
    await callbacks.on_log(f"[HunterSwarm · AI Search] Found {len(cands)} company candidates.")
    return cands, src


async def _search_linkedin_candidates(
    startup: StartupInput,
    icps: list[ICPProfile],
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> tuple[list[DiscoveredLeadCandidate], list[str]]:
    desired_qualified = getattr(startup, "target_qualified_leads", 10) or 10
    multiplier = 2.0 if startup.slaying_level.value == "RUTHLESS" else 1.5
    target_needed = max(startup.target_lead_count, min(60, int(desired_qualified * multiplier)))

    target_roles = list(dict.fromkeys(r for icp in icps for r in icp.target_roles))[:6]
    keywords = startup.product_name
    sources: list[str] = []
    browser_cands: list[DiscoveredLeadCandidate] = []

    # Path A: Live Harvey Playwright LinkedIn Automation (when LINKEDIN_EMAIL/PASSWORD + Playwright configured)
    if settings.linkedin_email and settings.linkedin_password and client is None:
        await callbacks.on_log(
            "[HunterSwarm · LinkedIn] Running Harvey LinkedIn browser search for target buyers..."
        )
        raw_profiles = await search_linkedin_via_harvey_browser(
            keywords=keywords,
            title=" ".join(target_roles[:2]),
            max_results=min(15, target_needed),
        )
        for prof in raw_profiles:
            comp = prof.get("company", "").strip()
            if not comp:
                continue
            full_name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
            browser_cands.append(
                DiscoveredLeadCandidate(
                    full_name=full_name or "LinkedIn Buyer",
                    role=prof.get("title", "Decision Maker") or "Decision Maker",
                    company=comp,
                    domain="",
                    industry=icps[0].name if icps else "Commercial",
                    employee_count=50,
                    funding_stage="Unknown",
                    tech_stack=[],
                    recent_signal=f"Active LinkedIn profile in {prof.get('location') or 'target market'}",
                    bio_snippet=f"Sourced directly via Harvey LinkedIn Search ({prof.get('linkedin_url', '')}).",
                    linkedin_url=prof.get("linkedin_url", ""),
                )
            )
        if browser_cands:
            sources.append("Harvey LinkedIn Browser")

    # Path B: Accountless LinkedIn X-Ray Search via Gemini Search Grounding (always works at $0!)
    if len(browser_cands) < target_needed:
        await callbacks.on_log(
            f"[HunterSwarm · LinkedIn] Discovering real LinkedIn decision-makers & company pages (site:linkedin.com/in, target: {target_needed})..."
        )
        icp_text = "\n".join(
            f"- {icp.name}: roles={icp.target_roles}, signals={icp.required_tech_signals}"
            for icp in icps
        )
        prompt = (
            f"Run LinkedIn X-Ray prospecting (`site:linkedin.com/in` and company research) to find "
            f"{target_needed} REAL named decision-makers (with their real title, real company name, "
            f"real company website domain, and LinkedIn profile URL if found) matching:\n"
            f"Seller Product: {startup.product_name} — {startup.description}\n"
            f"Target Buyer Profiles:\n{icp_text}\n\n"
            f"For EVERY person provide: full_name, exact LinkedIn job title, company name, clean official company domain (e.g. company.com), linkedin.com/in/... URL if surfaced, approximate headcount, industry, and why their current initiatives/posts make them relevant."
        )
        notes, urls, used_search = await _run_discovery_search(
            prompt,
            startup=startup,
            icps=icps,
            mode="LINKEDIN",
            target_count=target_needed,
            callbacks=callbacks,
            client=client,
        )
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        xray_cands = await _extract_structured_candidates(
            notes,
            urls,
            target_needed,
            callbacks,
            used_live_search=True if client is not None else used_search,
            client=client,
        )
        browser_cands.extend(xray_cands)
        sources.append("LinkedIn X-Ray Search" if used_search else "LinkedIn AI Prospecting")

    await callbacks.on_log(
        f"[HunterSwarm · LinkedIn] Discovered {len(browser_cands)} LinkedIn executive profiles."
    )
    return browser_cands, sources


def _merge_candidate_pools(
    ai_cands: list[DiscoveredLeadCandidate],
    li_cands: list[DiscoveredLeadCandidate],
    own_domain: str,
    limit: int,
) -> list[tuple[DiscoveredLeadCandidate, str]]:
    """
    Merges AI Search and LinkedIn Search outputs cleanly by normalized domain,
    preserving dual-source attribution ('AI Search + LinkedIn') when both find the same company.
    """
    by_domain: dict[str, tuple[DiscoveredLeadCandidate, str]] = {}
    ordered_keys: list[str] = []

    def _add(cand: DiscoveredLeadCandidate, label: str) -> None:
        clean_dom = _normalize_root_domain(cand.domain)
        if not clean_dom and cand.company:
            slug = "".join(ch for ch in cand.company.lower() if ch.isalnum())
            clean_dom = f"{slug}.com" if slug else ""
        if is_junk_or_self_domain(clean_dom, own_domain):
            return
        cand_clean = cand.model_copy(update={"domain": clean_dom})
        if clean_dom not in by_domain:
            by_domain[clean_dom] = (cand_clean, label)
            ordered_keys.append(clean_dom)
            return

        existing, prev_label = by_domain[clean_dom]
        # Prefer LinkedIn's named human decision-maker over generic AI Search label
        prefer_new_person = (
            "Team" in existing.full_name
            or "Leadership" in existing.full_name
            or bool(cand_clean.linkedin_url and not existing.linkedin_url)
        )
        merged_name = cand_clean.full_name if prefer_new_person else existing.full_name
        merged_role = cand_clean.role if prefer_new_person else existing.role
        merged_li = existing.linkedin_url or cand_clean.linkedin_url
        merged_stack = list(dict.fromkeys([*existing.tech_stack, *cand_clean.tech_stack]))
        merged_signal = existing.recent_signal
        if cand_clean.recent_signal and cand_clean.recent_signal not in merged_signal:
            merged_signal = f"{existing.recent_signal}; {cand_clean.recent_signal}".strip("; ")
        merged_label = (
            "AI Search + LinkedIn"
            if label != prev_label
            else label
        )
        by_domain[clean_dom] = (
            existing.model_copy(
                update={
                    "full_name": merged_name,
                    "role": merged_role,
                    "linkedin_url": merged_li,
                    "tech_stack": merged_stack,
                    "recent_signal": merged_signal,
                    "email_guess": existing.email_guess or cand_clean.email_guess,
                }
            ),
            merged_label,
        )

    for c in li_cands:
        _add(c, "LinkedIn")
    for c in ai_cands:
        _add(c, "AI Search")

    return [by_domain[k] for k in ordered_keys[:limit]]


async def discover_leads_via_harvey_and_search(
    startup: StartupInput,
    icps: list[ICPProfile],
    callbacks: PipelineCallbacks,
    active_sources: list[str],
    client: Any | None = None,
) -> tuple[list[LeadRecord], int, list[str]]:
    """
    Runs AI Search and/or LinkedIn Search (individually or combined), merges the results,
    enriches via Harvey Tier A collectors (multi-page crawl, people, ATS jobs) and
    Harvey Tier B Part 1 (DNS MX + pattern email builder), then emits on_leads_loaded.
    """
    use_ai = "AI_SEARCH" in active_sources
    use_li = "LINKEDIN_SEARCH" in active_sources

    tasks = []
    task_kinds = []
    if use_ai:
        tasks.append(_search_ai_candidates(startup, icps, callbacks, client=client))
        task_kinds.append("AI")
    if use_li:
        tasks.append(_search_linkedin_candidates(startup, icps, callbacks, client=client))
        task_kinds.append("LI")

    results = await asyncio.gather(*tasks)
    ai_cands: list[DiscoveredLeadCandidate] = []
    li_cands: list[DiscoveredLeadCandidate] = []
    source_labels: list[str] = []
    for kind, (cands, srcs) in zip(task_kinds, results):
        if kind == "AI":
            ai_cands.extend(cands)
        else:
            li_cands.extend(cands)
        for s in srcs:
            if s not in source_labels:
                source_labels.append(s)

    own_domain = _normalize_root_domain(startup.product_url)
    desired_qualified = getattr(startup, "target_qualified_leads", 10) or 10
    multiplier = 2.0 if startup.slaying_level.value == "RUTHLESS" else 1.5
    needed_pool = max(startup.target_lead_count, min(100, int(desired_qualified * multiplier)))
    merged = _merge_candidate_pools(ai_cands, li_cands, own_domain, needed_pool)

    await callbacks.on_log(
        f"[HunterSwarm] Merged {len(merged)} unique companies — running Harvey $0 site crawl, owner extractor, ATS job scan & DNS MX check..."
    )

    dossiers: dict[str, HarveyCompanyDossier] = {}
    probe_exec = GentleAdaptiveExecutor(concurrency=6, launch_stagger_s=0.03, max_retries=0)

    async def _probe_one(pair: tuple[DiscoveredLeadCandidate, str]) -> HarveyCompanyDossier:
        cand, _ = pair
        return await research_company_with_harvey(
            cand.domain,
            candidate_name=cand.full_name,
            candidate_role=cand.role,
            timeout_s=3.5,
        )

    url_ok = 0
    people_found = 0
    ats_found = 0
    mx_valid = 0
    async for pair, dossier in probe_exec.run_stream(merged, _probe_one):
        cand, _ = pair
        dossiers[cand.domain] = dossier
        if dossier.reachable:
            url_ok += 1
        if dossier.decision_makers:
            people_found += 1
        if dossier.ats_open_roles:
            ats_found += 1
        if dossier.mx_provider and dossier.mx_provider != "none":
            mx_valid += 1

    verified_pairs = [
        p for p in merged if dossiers.get(p[0].domain, HarveyCompanyDossier(False)).reachable
    ]
    active_pairs = verified_pairs if len(verified_pairs) >= 3 else merged

    discovered_leads: list[LeadRecord] = []
    for idx, (cand, channel_label) in enumerate(active_pairs, start=1):
        dossier = dossiers.get(cand.domain, HarveyCompanyDossier(reachable=False))
        merged_stack = list(dict.fromkeys([*cand.tech_stack, *dossier.tech_signals]))[:8]

        # Upgrade placeholder team names with Harvey's verified website owner/exec name
        final_name = cand.full_name.strip() or f"{cand.role} Team"
        final_role = cand.role.strip() or "Decision Maker"
        if (
            any(tok in final_name.lower() for tok in ("team", "leadership", "unknown", "decision maker"))
            and dossier.decision_makers
        ):
            top_dm = dossier.decision_makers[0]
            dm_name = f"{top_dm.get('first_name', '')} {top_dm.get('last_name', '')}".strip()
            if dm_name:
                final_name = dm_name
                if top_dm.get("title"):
                    final_role = top_dm["title"]

        # Choose best email from Harvey Tier B Part 1 -> AI candidate -> role fallback
        if dossier.resolved_email:
            chosen_email = dossier.resolved_email
            email_status = dossier.email_status
        elif cand.email_guess and "@" in cand.email_guess and "." in cand.email_guess:
            chosen_email = cand.email_guess.strip()
            email_status = "guess"
        else:
            chosen_email = f"contact@{cand.domain}"
            email_status = "invalid" if dossier.mx_provider == "none" else "guess"

        ats_note = (
            f" | Hiring ({dossier.ats_board_label}): {'; '.join(dossier.ats_open_roles[:2])}"
            if dossier.ats_open_roles
            else ""
        )
        site_note = f" | Site: {dossier.summary[:200]}" if dossier.summary else ""
        mx_note = (
            f" [MX: {dossier.mx_provider} · {email_status}]"
            if dossier.mx_provider
            else ""
        )
        li_note = f" [LinkedIn: {cand.linkedin_url}]" if cand.linkedin_url else ""

        discovered_leads.append(
            LeadRecord(
                id=f"disc_{idx:02d}",
                full_name=final_name,
                role=final_role,
                company=cand.company.strip(),
                domain=cand.domain,
                industry=cand.industry.strip() or "Commercial",
                employee_count=max(1, cand.employee_count),
                funding_stage=cand.funding_stage.strip() or "Unknown",
                tech_stack=merged_stack,
                recent_signal=f"{cand.recent_signal.strip()}{ats_note}".strip(),
                bio_snippet=f"{cand.bio_snippet.strip()}{site_note}{li_note}{mx_note}".strip(),
                email=chosen_email,
                linkedin_url=cand.linkedin_url,
                email_status=email_status,
                mx_provider=dossier.mx_provider,
                source_channel=channel_label,
            )
        )

    if not discovered_leads:
        raise RuntimeError(
            "Autonomous discovery found zero verifiable companies for this query. "
            "Try refining your product description or uploading a CSV."
        )

    source_labels.extend(["Harvey People & ATS", "Harvey MX + Pattern"])
    await callbacks.on_log(
        f"[HunterSwarm] Harvey enrichment complete: {len(discovered_leads)} companies "
        f"({url_ok} live sites, {people_found} exec teams, {ats_found} ATS boards, {mx_valid} MX-valid domains)."
    )
    return discovered_leads, url_ok, list(dict.fromkeys(source_labels))


async def _generate_hunt_queries(
    icps: list[ICPProfile], client: Any | None = None
) -> list[HuntQuery]:
    icp_summary = "\n".join(
        f"- {icp.name}: roles={icp.target_roles}, stack={icp.required_tech_signals}, triggers={icp.buying_triggers}"
        for icp in icps
    )
    genai_client = client or genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    async def _call_queries(_: int) -> list[HuntQuery]:
        resp = await genai_client.aio.models.generate_content(
            model=settings.gemini_workhorse_model,
            contents=f"ICPs:\n{icp_summary}",
            config=genai.types.GenerateContentConfig(
                system_instruction=(
                    "Generate 3 crisp B2B outbound hunt queries across relevant sources "
                    "(LinkedIn Sales Nav, Job/Hiring Boards, Industry/Storefront News Feeds) tailored to these ICPs."
                ),
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=HuntQueriesOutput,
            ),
        )
        if not resp.text:
            raise RuntimeError("HuntQueriesOutput empty")
        return HuntQueriesOutput.model_validate_json(resp.text).hunt_queries

    executor = GentleAdaptiveExecutor(concurrency=1, launch_stagger_s=0.0, max_retries=1)
    async for _, res in executor.run_stream([0], _call_queries):
        return res
    return []


async def _enrich_sparse_leads(
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
) -> tuple[list[LeadRecord], int, int]:
    """Enriches custom sparse CSV leads (missing tech_stack or recent_signal)."""
    sparse = [l for l in leads if not l.tech_stack or not l.recent_signal.strip()]
    if len(sparse) <= max(1, int(len(leads) * 0.2)):
        return leads, 0, 0

    await callbacks.on_log(
        f"[HunterSwarm] Detected {len(sparse)} sparse custom CSV leads — fetching sites & enriching via {settings.gemini_workhorse_model}..."
    )

    client = genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    site_snippets: dict[str, str] = {}
    url_ok = 0
    url_exec = GentleAdaptiveExecutor(concurrency=5, launch_stagger_s=0.03, max_retries=0)

    async def _fetch_one(lead: LeadRecord) -> str | None:
        return await fetch_site_context(f"https://{lead.domain}", timeout_s=2.0)

    async for lead, text in url_exec.run_stream(sparse[:25], _fetch_one):
        if text:
            site_snippets[lead.id] = text[:500]
            url_ok += 1

    batches = [sparse[i : i + 10] for i in range(0, len(sparse), 10)]
    patches_by_id: dict[str, tuple[list[str], str]] = {}

    async def _enrich_batch(batch: list[LeadRecord]) -> EnrichedLeadBatch:
        rows_desc = "\n".join(
            f"- {l.id}: {l.full_name}, {l.role} at {l.company} ({l.domain}) | site: {site_snippets.get(l.id, 'N/A')}"
            for l in batch
        )
        res = await client.aio.models.generate_content(
            model=settings.gemini_workhorse_model,
            contents=f"Infer likely tech_stack and recent_signal for these sparse B2B leads:\n{rows_desc}",
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EnrichedLeadBatch,
            ),
        )
        await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
        return EnrichedLeadBatch.model_validate_json(res.text or "{}")

    llm_exec = GentleAdaptiveExecutor(concurrency=3, launch_stagger_s=0.05, max_retries=1)
    async for _, batch_out in llm_exec.run_stream(batches, _enrich_batch):
        for p in batch_out.patches:
            patches_by_id[p.lead_id] = (p.inferred_tech_stack, p.inferred_signal)

    updated: list[LeadRecord] = []
    enriched_count = 0
    for lead in leads:
        if lead.id in patches_by_id:
            stack, sig = patches_by_id[lead.id]
            updated.append(
                lead.model_copy(
                    update={
                        "tech_stack": lead.tech_stack or stack,
                        "recent_signal": lead.recent_signal or sig,
                    }
                )
            )
            enriched_count += 1
        else:
            updated.append(lead)

    return updated, enriched_count, url_ok


async def execute_hunter_swarm(
    run_id: str,
    leads: list[LeadRecord],
    icps: list[ICPProfile],
    callbacks: PipelineCallbacks,
    startup: StartupInput | None = None,
    client: Any | None = None,
) -> tuple[list[LeadRecord], dict[str, HybridMatchContext], HunterReport]:
    await callbacks.on_phase(PipelinePhase.HUNTING)

    effective_sources = list(startup.lead_sources) if startup and startup.lead_sources else ["CSV_PRESET"]
    if startup and startup.auto_discover_leads and not any(
        s in effective_sources for s in ("AI_SEARCH", "LINKEDIN_SEARCH")
    ):
        effective_sources.append("AI_SEARCH")

    run_discovery = any(s in effective_sources for s in ("AI_SEARCH", "LINKEDIN_SEARCH")) or not leads
    autonomous_count = 0
    discovery_sources: list[str] = []
    enriched_count = 0
    url_ok = 0

    hunt_queries = await _generate_hunt_queries(icps, client=client)
    await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)

    updated_leads: list[LeadRecord] = []
    if run_discovery:
        if startup is None:
            raise RuntimeError("Autonomous lead discovery requires startup product context.")
        discovery_modes = [s for s in effective_sources if s in ("AI_SEARCH", "LINKEDIN_SEARCH")]
        if not discovery_modes:
            discovery_modes = ["AI_SEARCH"]

        disc_leads, disc_url_ok, disc_sources = await discover_leads_via_harvey_and_search(
            startup, icps, callbacks, active_sources=discovery_modes, client=client
        )
        autonomous_count = len(disc_leads)
        enriched_count = len(disc_leads)
        url_ok = disc_url_ok
        discovery_sources.extend(disc_sources)
        updated_leads.extend(disc_leads)

    if leads:
        csv_leads, csv_enriched, csv_urls = await _enrich_sparse_leads(leads, callbacks)
        enriched_count += csv_enriched
        url_ok += csv_urls
        discovery_sources.append("Uploaded / Preset Lead Dataset")
        existing_domains = {l.domain.lower() for l in updated_leads}
        for cl in csv_leads:
            if cl.domain.lower() not in existing_domains:
                updated_leads.append(cl)
                existing_domains.add(cl.domain.lower())

    if run_discovery:
        await callbacks.on_leads_loaded(updated_leads)

    memory_store = memory_registry.get_or_create(run_id)
    priors, emb_calls = await memory_store.index_and_score_leads(updated_leads)
    for _ in range(emb_calls):
        await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)

    report = HunterReport(
        hunt_queries=hunt_queries,
        enriched_sparse_leads=enriched_count,
        url_fetches_succeeded=url_ok,
        total_leads_ready=len(updated_leads),
        autonomous_discovered_leads=autonomous_count,
        discovery_sources=list(dict.fromkeys(discovery_sources)),
    )
    await callbacks.on_hunter_report(report)
    await callbacks.on_log(
        f"[HunterSwarm] Armed {len(updated_leads)} leads with Dual-Polarity priors ({emb_calls} embedding batches)."
    )
    return updated_leads, priors, report


class HunterSwarmADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_id: str
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        leads = [LeadRecord.model_validate(item) for item in ctx.session.state["leads"]]
        icps = [ICPProfile.model_validate(item) for item in ctx.session.state["icps"]]
        updated_leads, priors, report = await execute_hunter_swarm(
            self.run_id, leads, icps, self.callbacks, startup=startup
        )
        leads_list = [l.model_dump(mode="json") for l in updated_leads]
        priors_dict = {lid: p.model_dump(mode="json") for lid, p in priors.items()}
        report_dict = report.model_dump(mode="json")
        ctx.session.state["leads"] = leads_list
        ctx.session.state["hybrid_priors"] = priors_dict
        ctx.session.state["hunter_report"] = report_dict
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[genai.types.Part.from_text(text=f"Hunter armed {len(updated_leads)} leads")],
            ),
            actions=EventActions(
                state_delta={
                    "leads": leads_list,
                    "hybrid_priors": priors_dict,
                    "hunter_report": report_dict,
                }
            ),
        )
