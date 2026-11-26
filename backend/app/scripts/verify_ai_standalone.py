from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

# Ensure backend root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.interface import PipelineCallbacks
from app.agents.pipeline import run_live_pipeline
from app.agents.sniper_agent import resurrect_single_lead
from app.config import DATA_DIR, settings
from app.memory.exceptions import GeminiAPIUnavailableError
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    ModelId,
    PipelinePhase,
    SlayerVerdict,
    SlayingLevel,
    StartupInput,
)


class ConsoleCallbacks:
    """Real-time console telemetry logger for CLI verification."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.model_calls: dict[str, int] = {}

    async def on_phase(self, phase: PipelinePhase) -> None:
        print(f"\n⚡ [PHASE ENTER] >>> {phase.value}")

    async def on_log(self, message: str) -> None:
        if self.verbose:
            print(f"   [LOG] {message}")

    async def on_model_call(self, model_id: ModelId) -> None:
        val = model_id.value if hasattr(model_id, "value") else str(model_id)
        self.model_calls[val] = self.model_calls.get(val, 0) + 1

    async def on_audit(self, audit: MarketAuditResult) -> None:
        print(f"   [AUDIT RESULT] Readiness Score: {audit.market_readiness_score}/100")
        print(f"   [AUDIT RESULT] Value Prop: {audit.sharpened_value_prop}")
        print(f"   [AUDIT RESULT] Anti-ICP Flags ({len(audit.anti_icp_red_flags)}):")
        for flag in audit.anti_icp_red_flags:
            print(f"      ⛔ {flag}")

    async def on_icps(self, icps: list[ICPProfile]) -> None:
        print(f"   [ICPS CREATED] {len(icps)} Profiles generated:")
        for icp in icps:
            print(f"      🎯 [{icp.id}] {icp.name} | Roles: {', '.join(icp.target_roles)}")

    async def on_hunter_report(self, report: HunterReport) -> None:
        print(f"   [HUNTER REPORT] Ready Leads: {report.total_leads_ready} (Enriched: {report.enriched_sparse_leads})")

    async def on_verdict(self, verdict: SlayerVerdict) -> None:
        tag = "🟢 SURVIVED" if verdict.survived else "🔴 KILLED"
        print(f"   {tag}: {verdict.lead_id:<12} | {verdict.headline_tag:<32} (Score: {verdict.qualification_score:>2}/100)")

    async def on_email(self, draft: EmailDraft) -> None:
        print(f"\n   ✉️ [SNIPER DRAFTED] To: {draft.recipient_name} <{draft.recipient_email}> ({draft.company})")
        print(f"      Subject: {draft.subject}")
        print(f"      Evidence: \"{draft.email_evidence_phrase}\"")
        print(f"      Body:\n      {draft.body.strip()}\n")


async def main():
    print("=" * 80)
    print("LeadSlayer AI — Autonomous AI Engine Standalone Verification")
    print("Strict 3-Model Ecosystem: gemini-4-hydrogen, gemini-3.5-flash-lite, gemini-embedding-2")
    print("=" * 80)

    # 1. Load Data
    startup_path = DATA_DIR / "default_startup.json"
    leads_path = DATA_DIR / "leads_50.json"

    if not startup_path.exists() or not leads_path.exists():
        print(f"ERROR: Data files missing in {DATA_DIR}")
        sys.exit(1)

    with open(startup_path, "r", encoding="utf-8") as f:
        startup_data = json.load(f)
    with open(leads_path, "r", encoding="utf-8") as f:
        leads_raw = json.load(f)

    leads = [LeadRecord(**l) for l in leads_raw]
    print(f"Loaded {len(leads)} leads from {leads_path}")

    # ---------------------------------------------------------
    # TEST 1: RUTHLESS PIPELINE EXECUTION
    # ---------------------------------------------------------
    startup_ruthless = StartupInput(
        **{**startup_data, "slaying_level": SlayingLevel.RUTHLESS}
    )

    print("\n" + "=" * 80)
    print("RUN 1: RUTHLESS MODE PIPELINE (Target: ~76%-90% KILLED, ~6-10 SURVIVORS)")
    print("=" * 80)

    run_id_ruthless = f"cli_ruthless_{int(time.time())}"
    callbacks_ruthless = ConsoleCallbacks(verbose=True)

    t0 = time.time()
    result_ruthless = await run_live_pipeline(
        run_id=run_id_ruthless,
        startup_input=startup_ruthless,
        leads=leads,
        callbacks=callbacks_ruthless,
    )
    elapsed_ruthless = time.time() - t0

    survived_ruthless = [v for v in result_ruthless.verdicts.values() if v.survived]
    killed_ruthless = [v for v in result_ruthless.verdicts.values() if not v.survived]
    kill_rate = (len(killed_ruthless) / len(result_ruthless.verdicts)) * 100

    print("\n" + "-" * 80)
    print(f"RUTHLESS SUMMARY:")
    print(f"  Elapsed Time: {elapsed_ruthless:.2f}s")
    print(f"  Total Triaged: {len(result_ruthless.verdicts)}")
    print(f"  Killed: {len(killed_ruthless)} ({kill_rate:.1f}%)")
    print(f"  Survived: {len(survived_ruthless)}")
    print(f"  Emails Drafted: {len(result_ruthless.emails)}")
    print(f"  Model Telemetry: {callbacks_ruthless.model_calls}")
    print("-" * 80)

    # Validate evidence phrase in drafts
    for lead_id, draft in result_ruthless.emails.items():
        assert draft.email_evidence_phrase in draft.body, (
            f"Evidence phrase '{draft.email_evidence_phrase}' not found in body for lead {lead_id}!"
        )

    print("✅ All surviving EmailDrafts contain verbatim email_evidence_phrase in body!")

    # ---------------------------------------------------------
    # TEST 2: RESURRECT SINGLE LEAD
    # ---------------------------------------------------------
    if killed_ruthless:
        sample_killed = killed_ruthless[0]
        killed_lead = next(l for l in leads if l.id == sample_killed.lead_id)
        target_icp = result_ruthless.icps[0]

        print("\n" + "=" * 80)
        print(f"RUN 2: ON-DEMAND RESURRECTION TEST on lead {killed_lead.id} ({killed_lead.company})")
        print("=" * 80)

        new_verdict, res_draft = await resurrect_single_lead(
            run_id=run_id_ruthless,
            lead=killed_lead,
            old_verdict=sample_killed,
            icp=target_icp,
        )

        print(f"Resurrected Verdict: survived={new_verdict.survived}, tag='{new_verdict.headline_tag}'")
        print(f"Resurrected Email Subject: '{res_draft.subject}'")
        print(f"Evidence Phrase: \"{res_draft.email_evidence_phrase}\"")
        print(f"Body:\n{res_draft.body.strip()}\n")
        assert res_draft.email_evidence_phrase in res_draft.body
        print("✅ Resurrect single lead succeeded with evidence guarantee!")

    # ---------------------------------------------------------
    # TEST 3: LENIENT MODE COMPARISON
    # ---------------------------------------------------------
    startup_lenient = StartupInput(
        **{**startup_data, "slaying_level": SlayingLevel.LENIENT}
    )

    print("\n" + "=" * 80)
    print("RUN 3: LENIENT MODE PIPELINE (Confirming strictly more leads survive than RUTHLESS)")
    print("=" * 80)

    run_id_lenient = f"cli_lenient_{int(time.time())}"
    callbacks_lenient = ConsoleCallbacks(verbose=False)

    result_lenient = await run_live_pipeline(
        run_id=run_id_lenient,
        startup_input=startup_lenient,
        leads=leads,
        callbacks=callbacks_lenient,
    )

    survived_lenient = [v for v in result_lenient.verdicts.values() if v.survived]
    killed_lenient = [v for v in result_lenient.verdicts.values() if not v.survived]

    print(f"LENIENT Results: {len(survived_lenient)} survived, {len(killed_lenient)} killed.")
    print(f"RUTHLESS Results: {len(survived_ruthless)} survived, {len(killed_ruthless)} killed.")

    assert len(survived_lenient) > len(survived_ruthless), (
        f"Expected LENIENT survivors ({len(survived_lenient)}) > RUTHLESS survivors ({len(survived_ruthless)})"
    )
    print("✅ LENIENT mode passed strictly more leads than RUTHLESS mode!")

    print("\n" + "=" * 80)
    print("ALL STANDALONE AI ENGINE VERIFICATION CHECKS PASSED 100%!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except GeminiAPIUnavailableError as exc:
        print(f"\n❌ [GEMINI ERROR]: {exc.user_message}")
        if exc.raw_error:
            print(f"   Details: {exc.raw_error}")
        sys.exit(1)
