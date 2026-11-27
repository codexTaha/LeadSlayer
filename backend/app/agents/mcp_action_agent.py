from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.key_rotator import key_rotator
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.config import settings
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    MCPToolCallRecord,
    ModelId,
    SlayerVerdict,
    StartupInput,
)
from app.services.mcp_client import build_adk_mcp_toolset


def _summarize_args(tool_name: str, args: dict[str, Any]) -> str:
    safe_keys = (
        "domain",
        "company",
        "action",
        "lead_id",
        "recipient_email",
        "delivery_mode",
        "priority",
        "due_in_days",
        "run_id",
        "product_name",
    )
    parts = [f"{k}={args[k]!r}" for k in safe_keys if k in args and args[k] not in ("", None)]
    if not parts:
        keys = [k for k in args.keys() if "password" not in k.lower() and "secret" not in k.lower()]
        return ", ".join(keys[:4])
    return ", ".join(parts[:5])


def _infer_decision_reason(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "check_and_update_dnc_crm":
        return f"Verify CRM & Do-Not-Contact status for {args.get('company') or args.get('domain', 'lead')}"
    if tool_name == "schedule_followup_reminder":
        return (
            f"High-urgency signal on {args.get('company', args.get('lead_id', 'lead'))} "
            f"-> create {args.get('due_in_days', 2)}-day .ics follow-up ({args.get('priority', 'HIGH')})"
        )
    if tool_name == "stage_or_dispatch_email_mcp":
        return (
            f"Validate & stage grounded draft for {args.get('recipient_email', 'survivor')} "
            f"through deliverability gate ({args.get('delivery_mode', 'SANDBOX')})"
        )
    if tool_name == "save_campaign_artifacts":
        return f"Persist campaign brief & audit artifacts to exports/{args.get('run_id', 'run')}/"
    return f"Autonomous agent selected MCP tool `{tool_name}`"


def _extract_response_text(resp_obj: Any) -> str:
    if isinstance(resp_obj, dict):
        # MCPTool outputs often arrive as {'result': '...json...'} or {'content': [{'text': '...'}]}
        if isinstance(resp_obj.get("result"), str):
            return resp_obj["result"]
        content = resp_obj.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                return first["text"]
        return json.dumps(resp_obj)
    return str(resp_obj or "")


async def execute_mcp_outreach_actions(
    run_id: str,
    startup: StartupInput,
    audit: MarketAuditResult,
    leads: list[LeadRecord],
    verdicts: dict[str, SlayerVerdict],
    emails: dict[str, EmailDraft],
    callbacks: PipelineCallbacks,
    toolset: Any | None = None,
) -> list[MCPToolCallRecord]:
    """
    Runs an autonomous ADK LlmAgent equipped with LeadSlayer's stdio MCP toolset.
    The agent decides per-survivor which CRM, follow-up calendar, deliverability gate,
    and artifact export MCP tools to invoke, streaming every decision in real time.
    """
    survivors = [l for l in leads if verdicts.get(l.id) and verdicts[l.id].survived]
    killed_n = sum(1 for v in verdicts.values() if not v.survived)

    await callbacks.on_log(
        f"[OutreachMCPAgent] Connecting ADK LlmAgent to leadslayer-ops-mcp over stdio for {len(survivors)} survivors..."
    )

    survivor_lines: list[str] = []
    for lead in survivors[:12]:
        v = verdicts[lead.id]
        d = emails.get(lead.id)
        survivor_lines.append(
            f"- lead_id={lead.id} | name={lead.full_name} | company={lead.company} | domain={lead.domain} "
            f"| email={lead.email} | email_status={lead.email_status} | mx={lead.mx_provider or 'unknown'} "
            f"| qual_score={v.qualification_score} | signal={lead.recent_signal[:120]!r}\n"
            f"  draft_subject={d.subject if d else 'N/A'!r} | draft_body={(d.body if d else '')[:280]!r}"
        )

    instruction = (
        "You are LeadSlayer's Autonomous GTM Operations Coordinator backed by an MCP server (`leadslayer-ops-mcp`).\n"
        "You MUST inspect the surviving leads and execute concrete operational decisions using your MCP tools:\n"
        "1. Call `check_and_update_dnc_crm(domain=..., company=..., action='check')` on surviving lead domains to verify none are blocked.\n"
        "2. For high-urgency survivors (`qual_score >= 82`), call `schedule_followup_reminder` (`priority='HIGH'`, `due_in_days=2`).\n"
        "3. For CRM-clear survivors with a drafted email, call `stage_or_dispatch_email_mcp` using `delivery_mode='SANDBOX'` "
        "to validate them through the deterministic deliverability gate.\n"
        "4. Finally, call `save_campaign_artifacts(run_id=..., product_name=..., summary_markdown=...)` ONCE with a crisp executive summary.\n"
        "Only pass actual lead data provided in the prompt. Never fabricate leads or emails."
    )

    user_prompt = (
        f"Run ID: {run_id}\n"
        f"Product: {startup.product_name} ({startup.product_url or 'N/A'})\n"
        f"Sharpened Value Prop: {audit.sharpened_value_prop}\n"
        f"Campaign Stats: {len(leads)} evaluated, {killed_n} killed, {len(survivors)} survived.\n\n"
        f"SURVIVORS TO ACTION VIA MCP:\n"
        + ("\n".join(survivor_lines) if survivor_lines else "None (0 survivors). Call save_campaign_artifacts with a brief 0-survivor diagnostic summary.")
    )

    owns_toolset = toolset is None
    active_toolset = toolset or build_adk_mcp_toolset(timeout=15.0)
    records: list[MCPToolCallRecord] = []
    pending_by_call_id: dict[str, MCPToolCallRecord] = {}

    async def _run_mcp_agent(_: int) -> list[MCPToolCallRecord]:
        active_key = key_rotator.next_key()
        if active_key:
            os.environ["GOOGLE_API_KEY"] = active_key
        mcp_agent = LlmAgent(
            name="outreach_mcp_coordinator",
            model=settings.gemini_brain_model,
            instruction=instruction,
            tools=[active_toolset],
            generate_content_config=genai.types.GenerateContentConfig(temperature=0.1),
        )
        session_service = InMemorySessionService()
        sid = f"mcp_{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name="leadslayer_mcp_ops",
            user_id="founder",
            session_id=sid,
        )
        runner = Runner(
            app_name="leadslayer_mcp_ops",
            agent=mcp_agent,
            session_service=session_service,
        )
        msg = genai.types.Content(
            role="user",
            parts=[genai.types.Part.from_text(text=user_prompt)],
        )

        async for ev in runner.run_async(
            user_id="founder",
            session_id=sid,
            new_message=msg,
        ):
            for fc in ev.get_function_calls() or []:
                fc_id = getattr(fc, "id", None) or uuid.uuid4().hex[:8]
                args = dict(getattr(fc, "args", None) or {})
                tool_name = str(getattr(fc, "name", "unknown_mcp_tool"))
                rec = MCPToolCallRecord(
                    id=fc_id,
                    timestamp_ms=int(time.time() * 1000),
                    agent_name="OutreachMCPAgent",
                    decision_reason=_infer_decision_reason(tool_name, args),
                    server_name="leadslayer-ops-mcp",
                    tool_name=tool_name,
                    arguments_summary=_summarize_args(tool_name, args),
                    result_summary="Executing via stdio MCP...",
                    status="CALLED",
                )
                pending_by_call_id[fc_id] = rec
                await callbacks.on_log(
                    f"[MCP DECISION] {rec.decision_reason} -> calling `{tool_name}`"
                )

            for fr in ev.get_function_responses() or []:
                fr_id = getattr(fr, "id", None) or ""
                tool_name = str(getattr(fr, "name", "unknown_mcp_tool"))
                resp_text = _extract_response_text(getattr(fr, "response", None))
                status: str = "SUCCEEDED"
                if '"BLOCKED"' in resp_text or '"allowed": false' in resp_text.lower():
                    status = "BLOCKED"
                elif '"error"' in resp_text.lower() and '"error": ""' not in resp_text:
                    status = "FAILED"

                base = pending_by_call_id.pop(fr_id, None)
                if base is None:
                    base = MCPToolCallRecord(
                        id=fr_id or uuid.uuid4().hex[:8],
                        timestamp_ms=int(time.time() * 1000),
                        agent_name="OutreachMCPAgent",
                        decision_reason=f"Agent invoked MCP tool `{tool_name}`",
                        server_name="leadslayer-ops-mcp",
                        tool_name=tool_name,
                        arguments_summary="",
                    )
                finished = base.model_copy(
                    update={
                        "result_summary": resp_text[:220],
                        "status": status,
                    }
                )
                records.append(finished)
                if hasattr(callbacks, "on_mcp_tool_call"):
                    await callbacks.on_mcp_tool_call(finished)
                await callbacks.on_log(
                    f"[MCP RESULT] `{tool_name}` -> {finished.status}: {finished.result_summary[:110]}"
                )

        return records

    try:
        executor = GentleAdaptiveExecutor(
            concurrency=1, launch_stagger_s=0.0, max_retries=1, backoff_schedule=(2.0,)
        )
        async for _, done_records in executor.run_stream([0], _run_mcp_agent):
            records = done_records
    finally:
        if owns_toolset:
            try:
                await active_toolset.close()
            except Exception:
                pass

    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_log(
        f"[OutreachMCPAgent] Completed {len(records)} autonomous MCP tool call(s) on leadslayer-ops-mcp."
    )
    return records


class McpActionADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_id: str
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        audit = MarketAuditResult.model_validate(ctx.session.state["market_audit"])
        leads = [LeadRecord.model_validate(item) for item in ctx.session.state["leads"]]
        verdicts = {
            lid: SlayerVerdict.model_validate(raw)
            for lid, raw in ctx.session.state.get("verdicts", {}).items()
        }
        emails = {
            lid: EmailDraft.model_validate(raw)
            for lid, raw in ctx.session.state.get("emails", {}).items()
        }

        records = await execute_mcp_outreach_actions(
            run_id=self.run_id,
            startup=startup,
            audit=audit,
            leads=leads,
            verdicts=verdicts,
            emails=emails,
            callbacks=self.callbacks,
        )
        serialized = [r.model_dump(mode="json") for r in records]
        ctx.session.state["mcp_tool_calls"] = serialized
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[
                    genai.types.Part.from_text(
                        text=f"Executed {len(records)} MCP actions"
                    )
                ],
            ),
            actions=EventActions(state_delta={"mcp_tool_calls": serialized}),
        )
