from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.pipeline import run_live_pipeline
from app.agents.sniper_agent import resurrect_single_lead
from app.memory.exceptions import GeminiAPIUnavailableError
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    MarketAuditResult,
    MCPToolCallRecord,
    ModelId,
    PipelinePhase,
    SlayerVerdict,
    SlayingLevel,
)
from app.services.lead_loader import load_default_startup, load_preset_leads


class ConsoleCallbacks:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.model_calls: dict[str, int] = {}

    async def on_phase(self, phase: PipelinePhase) -> None:
        print(f"\n>> PHASE: {phase.value}", flush=True)

    async def on_log(self, message: str) -> None:
        if self.verbose:
            print(f"   [LOG] {message}", flush=True)

    async def on_model_call(self, model_id: ModelId) -> None:
        self.model_calls[model_id.value] = self.model_calls.get(model_id.value, 0) + 1

    async def on_audit(self, audit: MarketAuditResult) -> None:
        print(
            f"   [AUDIT] Readiness={audit.market_readiness_score}/100 | "
            f"Gaps={len(audit.assumption_gaps)} | Competitors={len(audit.competitor_landscape)} | "
            f"Anti-ICP Rules={len(audit.anti_icp_red_flags)}",
            flush=True,
        )

    async def on_icps(self, icps: list[ICPProfile]) -> None:
        print(f"   [ICPS] {[icp.name for icp in icps]}", flush=True)

    async def on_leads_loaded(self, leads) -> None:
        print(f"   [LEADS] {len(leads)} leads loaded", flush=True)

    async def on_hunter_report(self, report: HunterReport) -> None:
        print(
            f"   [HUNTER] {len(report.hunt_queries)} queries synthesized | {report.total_leads_ready} leads ready",
            flush=True,
        )

    async def on_verdict(self, verdict: SlayerVerdict) -> None:
        if self.verbose:
            badge = "SURVIVED" if verdict.survived else "KILLED  "
            print(
                f"   [{badge}] {verdict.lead_id} | {verdict.headline_tag:<30} | score={verdict.qualification_score}",
                flush=True,
            )

    async def on_email(self, draft: EmailDraft) -> None:
        print(
            f"   [EMAIL] {draft.lead_id} -> {draft.recipient_name} ({draft.company}) | "
            f"Subj: {draft.subject!r} | span_ok={draft.email_evidence_phrase in draft.body}",
            flush=True,
        )

    async def on_mcp_tool_call(self, record: MCPToolCallRecord) -> None:
        print(
            f"   [MCP] {record.tool_name} ({record.status}) | {record.decision_reason}",
            flush=True,
        )


async def main() -> None:
    startup = load_default_startup()
    leads = load_preset_leads()

    print("=" * 72)
    print("LeadSlayer AI — Standalone ADK 2.0 Verification (RUTHLESS Mode)")
    print("=" * 72)

    t0 = time.perf_counter()
    res = await run_live_pipeline(
        run_id=f"standalone_{int(time.time())}",
        startup_input=startup.model_copy(update={"slaying_level": SlayingLevel.RUTHLESS}),
        leads=leads,
        callbacks=ConsoleCallbacks(verbose=True),
    )
    dt = time.perf_counter() - t0

    killed = [v for v in res.verdicts.values() if not v.survived]
    survived = [v for v in res.verdicts.values() if v.survived]
    print("\n" + "-" * 72)
    print(f"DONE in {dt:.2f}s | Killed: {len(killed)}/50 | Survived: {len(survived)}/50 | Emails: {len(res.emails)}")
    for lid, draft in res.emails.items():
        assert draft.email_evidence_phrase in draft.body, f"Missing evidence span for {lid}"
    print("All EmailDraft evidence phrases verified inside bodies.")

    if killed:
        sample = killed[0]
        killed_lead = next(l for l in leads if l.id == sample.lead_id)
        new_verdict, res_draft = await resurrect_single_lead(
            res.run_id, killed_lead, sample, res.icps[0]
        )
        assert new_verdict.survived and new_verdict.resurrected_by_user
        assert res_draft.email_evidence_phrase in res_draft.body
        print(f"Resurrect check passed on {killed_lead.id} ({killed_lead.company}).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except GeminiAPIUnavailableError as exc:
        print(f"\n[GEMINI ERROR] {exc.user_message} ({exc.raw_error})")
        sys.exit(1)
