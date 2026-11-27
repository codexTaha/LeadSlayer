from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.key_rotator import key_rotator
from app.agents.prompts import AUDITOR_SYSTEM_PROMPT
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.config import settings
from app.harvey_bridge.web_index import has_live_web_index, query_live_web_index
from app.models.schemas import MarketAuditResult, ModelId, PipelinePhase, StartupInput
from app.services.url_fetcher import fetch_site_context


async def _run_optional_search_grounding(product_name: str, description: str) -> str | None:
    """
    Lightweight optional live market context pass for real competitor & switching context.
    Prefers our encapsulated live web index when active, then unblocked search keys.
    Never fails the pipeline or spams logs if search grounding is unavailable or throttled.
    """
    if has_live_web_index():
        try:
            notes, _ = await query_live_web_index(
                [f"{product_name} competitors alternatives pricing switching"],
                num_per_query=6,
                pages_per_query=1,
            )
            if notes:
                return notes[:1400]
        except Exception:
            pass

    search_key = key_rotator.next_search_key()
    if not search_key:
        return None
    try:
        client = genai.Client(
            api_key=search_key,
            http_options=genai.types.HttpOptions(
                retry_options=genai.types.HttpRetryOptions(attempts=1)
            ),
        )
        res = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Briefly list 3 real competing products and common buyer switching triggers "
                f"for this category in 4 concise bullets.\nProduct: {product_name}\n"
                f"Description: {description}"
            ),
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        text = (res.text or "").strip()
        if text:
            key_rotator.mark_search_ok(search_key)
            return text
        return None
    except Exception as exc:
        if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "404" in str(exc):
            key_rotator.mark_search_throttled(search_key)
        return None


async def execute_market_audit(
    startup: StartupInput,
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> MarketAuditResult:
    await callbacks.on_phase(PipelinePhase.AUDITING)
    await callbacks.on_log(
        f"[MarketAuditor] Initializing autonomous ADK LlmAgent on {settings.gemini_brain_model}..."
    )

    if client is not None:
        site_context = await fetch_site_context(startup.product_url, timeout_s=3.0)
        search_notes = await _run_optional_search_grounding(
            startup.product_name, startup.description
        )
        prompt_parts = [
            f"Product Name: {startup.product_name}",
            f"Product URL: {startup.product_url or 'N/A'}",
            f"Product Description:\n{startup.description}",
            f"Founder's Market Assumptions:\n{startup.founder_assumptions}",
        ]
        if site_context:
            prompt_parts.append(f"Live Website Content:\n{site_context}")
        if search_notes:
            prompt_parts.append(f"Live Search Market Intel:\n{search_notes}")
        user_prompt = "\n\n".join(prompt_parts)

        async def _call_auditor_stub(_: int) -> MarketAuditResult:
            resp = await client.aio.models.generate_content(
                model=settings.gemini_brain_model,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=AUDITOR_SYSTEM_PROMPT,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=MarketAuditResult,
                ),
            )
            if not resp.text:
                raise RuntimeError("MarketAuditor returned empty output.")
            audit = MarketAuditResult.model_validate_json(resp.text)
            return audit.model_copy(
                update={
                    "url_scraped_context_used": bool(site_context),
                    "search_grounding_used": bool(search_notes),
                }
            )

        executor = GentleAdaptiveExecutor(
            concurrency=1,
            launch_stagger_s=0.0,
            max_retries=max(2, key_rotator.pool_size),
            backoff_schedule=(1.5, 3.0),
        )
        audit_result: MarketAuditResult | None = None
        async for _, res in executor.run_stream([0], _call_auditor_stub):
            audit_result = res
        assert audit_result is not None
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        await callbacks.on_audit(audit_result)
        return audit_result

    flags = {"url_used": False, "search_used": False}

    async def fetch_product_website(url: str) -> str:
        """Fetch and extract live landing page copy from a public startup URL."""
        text = await fetch_site_context(url, timeout_s=3.5)
        if text:
            flags["url_used"] = True
            await callbacks.on_log(
                f"[MarketAuditor · Tool] fetch_product_website({url}) succeeded ({len(text)} chars)."
            )
            return text
        await callbacks.on_log(
            f"[MarketAuditor · Tool] Website unreachable/empty for {url} -> agent adapting to search intel."
        )
        return "WEBSITE_UNREACHABLE_OR_EMPTY: Use search_market_intel to inspect live competitor positioning."

    async def search_market_intel(product_name: str, category_description: str) -> str:
        """Run Google Search / live index grounding to retrieve real competitors and buyer switching triggers."""
        notes = await _run_optional_search_grounding(product_name, category_description)
        if notes:
            flags["search_used"] = True
            await callbacks.on_log(
                "[MarketAuditor · Tool] search_market_intel returned live competitive landscape."
            )
            return notes
        return "SEARCH_INTEL_UNAVAILABLE: Base competitive insights on product description and domain knowledge."

    adaptive_instruction = (
        AUDITOR_SYSTEM_PROMPT
        + "\n\nAUTONOMOUS TOOL-USE POLICY:\n"
        "- If a Product URL is provided (not 'N/A'), call `fetch_product_website(url)` first to verify live product positioning.\n"
        "- If `fetch_product_website` fails, returns WEBSITE_UNREACHABLE_OR_EMPTY, or lacks competitive context, "
        "autonomously pivot and call `search_market_intel(product_name, description)` before producing your final MarketAuditResult.\n"
        "- Once you have sufficient market context, emit the final structured MarketAuditResult JSON."
    )

    user_prompt = (
        f"Product Name: {startup.product_name}\n"
        f"Product URL: {startup.product_url or 'N/A'}\n"
        f"Product Description:\n{startup.description}\n\n"
        f"Founder's Market Assumptions:\n{startup.founder_assumptions}"
    )

    async def _run_adk_auditor(_: int) -> MarketAuditResult:
        active_key = key_rotator.next_key()
        if active_key:
            os.environ["GOOGLE_API_KEY"] = active_key
        try:
            auditor_llm = LlmAgent(
                name="market_auditor_llm",
                model=settings.gemini_brain_model,
                instruction=adaptive_instruction,
                tools=[
                    FunctionTool(fetch_product_website),
                    FunctionTool(search_market_intel),
                ],
                output_schema=MarketAuditResult,
                output_key="market_audit_out",
                generate_content_config=genai.types.GenerateContentConfig(temperature=0.2),
            )
            session_service = InMemorySessionService()
            sid = f"audit_{uuid.uuid4().hex[:8]}"
            await session_service.create_session(
                app_name="leadslayer_auditor",
                user_id="founder",
                session_id=sid,
            )
            runner = Runner(
                app_name="leadslayer_auditor",
                agent=auditor_llm,
                session_service=session_service,
            )
            msg = genai.types.Content(
                role="user",
                parts=[genai.types.Part.from_text(text=user_prompt)],
            )
            last_text = ""
            async for ev in runner.run_async(
                user_id="founder",
                session_id=sid,
                new_message=msg,
            ):
                for fc in ev.get_function_calls() or []:
                    if fc.name != "set_model_response":
                        await callbacks.on_log(
                            f"[MarketAuditor · Decision] Invoking `{fc.name}` tool..."
                        )
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "text", None):
                            last_text = p.text

            final_session = await session_service.get_session(
                app_name="leadslayer_auditor",
                user_id="founder",
                session_id=sid,
            )
            raw_out = (final_session.state if final_session else {}).get("market_audit_out")
            if raw_out is not None:
                parsed = (
                    raw_out
                    if isinstance(raw_out, MarketAuditResult)
                    else MarketAuditResult.model_validate(raw_out)
                    if isinstance(raw_out, dict)
                    else MarketAuditResult.model_validate_json(str(raw_out))
                )
            elif last_text.strip():
                parsed = MarketAuditResult.model_validate_json(last_text)
            else:
                raise RuntimeError("MarketAuditor ADK LlmAgent returned empty output.")

            if active_key:
                key_rotator.mark_ok(active_key)
        except Exception as exc:
            if active_key and ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)):
                key_rotator.mark_throttled(active_key)
            raise

        return parsed.model_copy(
            update={
                "url_scraped_context_used": flags["url_used"],
                "search_grounding_used": flags["search_used"],
            }
        )

    executor = GentleAdaptiveExecutor(
        concurrency=1,
        launch_stagger_s=0.0,
        max_retries=max(2, key_rotator.pool_size),
        backoff_schedule=(1.5, 3.0),
    )
    audit_result: MarketAuditResult | None = None
    async for _, res in executor.run_stream([0], _run_adk_auditor):
        audit_result = res

    assert audit_result is not None
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_audit(audit_result)
    await callbacks.on_log(
        f"[MarketAuditor] Readiness {audit_result.market_readiness_score}/100 · Locked {len(audit_result.anti_icp_red_flags)} Anti-ICP kill rules."
    )
    return audit_result


class MarketAuditorADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        audit = await execute_market_audit(startup, self.callbacks)
        audit_dict = audit.model_dump(mode="json")
        ctx.session.state["market_audit"] = audit_dict
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[genai.types.Part.from_text(text=audit.sharpened_value_prop)],
            ),
            actions=EventActions(state_delta={"market_audit": audit_dict}),
        )
