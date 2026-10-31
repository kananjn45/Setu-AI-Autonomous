"""
SETTLE.AI - Phase 1 Scripted Scenarios Demonstration Runner
Executes the 5 canonical scenarios and prints the deterministic decision outputs.
"""

import sys
import json

# Ensure stdout encodes UTF-8 for Indian Rupee symbol on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from settle_ai.agent.schemas import (
    DisputeGrievance,
    DisputeChannel,
    BankStatus,
    SoundboxStatus,
    CanonicalTxState,
)
from settle_ai.agent.tools import (
    bank_tool,
    soundbox_tool,
    ledger_tool,
    reset_sandbox_state,
)
from settle_ai.agent.orchestrator import SettleOrchestrator
from settle_ai.agent.state_resolver import TransactionStateResolver
from settle_ai.agent.audit_logger import audit_logger

def run_scenarios():
    print("=" * 80)
    print("SETU (Team 0 and 1) - PHASE 1: CORE CORRECTNESS VERIFICATION")
    print("=" * 80)

    # -------------------------------------------------------------
    # Scenario 1: Credited / Packet Dropped
    # -------------------------------------------------------------
    reset_sandbox_state()
    orchestrator = SettleOrchestrator()
    rrn1 = "112233445566"
    bank_tool.register_transaction(rrn=rrn1, amount=500.0, status=BankStatus.SUCCESS, payer_bank="Axis Bank")
    soundbox_tool._devices["SB_DELHI_0841"]["status"] = SoundboxStatus.PACKET_DROPPED
    soundbox_tool._devices["SB_DELHI_0841"]["volume"] = 80

    g1 = DisputeGrievance(
        dispute_id="DSP_SCENARIO_1",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn=rrn1,
        amount=500.0,
        voice_transcript="Bhaiya ₹500 ka payment aaya par Soundbox nahi bola",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Gupta Tea Stall",
    )
    s1 = orchestrator.resolve_dispute(g1)
    print("\n[SCENARIO 1: CREDITED / PACKET DROPPED]")
    print(f"  Input: Grievance for ₹{s1.amount:.2f} (RRN: {s1.rrn})")
    print(f"  Canonical State    : {s1.canonical_state.value}")
    print(f"  Root Cause Label   : {s1.root_cause_label.value}")
    print(f"  Chime Guard Passed : {s1.soundbox_pushed} (Audio pushed with last 4 UTR: {s1.rrn[-4:]})")
    print(f"  Ledger Credited    : {s1.ledger_credited}")
    print(f"  Audit Block Hash   : {s1.audit_hash_sha256[:16]}...")

    # -------------------------------------------------------------
    # Scenario 2: Device Muted / Diagnosed
    # -------------------------------------------------------------
    reset_sandbox_state()
    orchestrator = SettleOrchestrator()
    rrn2 = "223344556677"
    soundbox_tool._devices["SB_DELHI_0841"]["volume"] = 0
    soundbox_tool._devices["SB_DELHI_0841"]["status"] = SoundboxStatus.MUTED
    bank_tool.register_transaction(rrn=rrn2, amount=450.0, status=BankStatus.SUCCESS, payer_bank="ICICI Bank")

    g2 = DisputeGrievance(
        dispute_id="DSP_SCENARIO_2",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn=rrn2,
        amount=450.0,
        voice_transcript="Soundbox bilkul aawaz nahi kar raha",
        channel=DisputeChannel.INDIC_VOICE,
    )
    s2 = orchestrator.resolve_dispute(g2)
    print("\n[SCENARIO 2: DEVICE MUTED / TELEMETRY DIAGNOSIS]")
    print(f"  Input: Grievance 'Soundbox bilkul aawaz nahi kar raha'")
    print(f"  Telemetry Diagnosis: Volume was 0% (Muted)")
    print(f"  Remote Action      : {s2.device_remediation_applied}")
    print(f"  Root Cause Label   : {s2.root_cause_label.value}")
    print(f"  Device Volume Now  : {soundbox_tool._devices['SB_DELHI_0841']['volume']}%")
    print(f"  Chime Replay       : Dispatched after restoring volume ({s2.soundbox_pushed})")

    # -------------------------------------------------------------
    # Scenario 3: Failed / Reversal Due (RBI TAT)
    # -------------------------------------------------------------
    reset_sandbox_state()
    orchestrator = SettleOrchestrator()
    rrn3 = "334455667788"
    bank_tool.register_transaction(
        rrn=rrn3,
        amount=800.0,
        status=BankStatus.REVERSAL_INITIATED,
        payer_bank="State Bank of India",
        raw_message="Customer account debited, switch clearing failed.",
    )

    g3 = DisputeGrievance(
        dispute_id="DSP_SCENARIO_3",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn=rrn3,
        amount=800.0,
        voice_transcript="Customer ke phone se 800 kate par mere paas nahi aaye",
    )
    s3 = orchestrator.resolve_dispute(g3)
    _, p3 = TransactionStateResolver.resolve_state("MERCH_GUPTA_TEA", 800.0, rrn3)
    print("\n[SCENARIO 3: FAILED / AUTO-REVERSAL DUE (RBI TAT HARMONISED)]")
    print(f"  Input: RRN {s3.rrn} for ₹{s3.amount:.2f}")
    print(f"  Canonical State    : {s3.canonical_state.value}")
    print(f"  Root Cause Label   : {s3.root_cause_label.value}")
    print(f"  Chime Guard Action : BLOCKED (Can replay: {p3['can_replay_chime']})")
    print(f"  RBI TAT Framework  : Customer auto-reversal within T+{p3['rbi_tat_days']} day(s)")
    print(f"  Delay Compensation : ₹{p3['compensation_per_day']:.0f}/day beyond TAT circular")
    print(f"  SETU Explanation   : {p3['response_message']}")

    # -------------------------------------------------------------
    # Scenario 4: Ambiguous / Clarifying Question
    # -------------------------------------------------------------
    reset_sandbox_state()
    bank_tool.register_transaction(rrn="445566778811", amount=500.0, status=BankStatus.SUCCESS, payer_bank="Axis Bank")
    bank_tool.register_transaction(rrn="445566778822", amount=500.0, status=BankStatus.SUCCESS, payer_bank="HDFC Bank")

    s4_state, s4_payload = TransactionStateResolver.resolve_state(
        merchant_id="MERCH_GUPTA_TEA",
        amount=500.0,
        rrn=None,
    )
    print("\n[SCENARIO 4: AMBIGUOUS (MULTIPLE MATCHES) / CLARIFYING QUESTION]")
    print(f"  Input: Counter query without RRN: 'Setu, ₹500 aaya kya?'")
    print(f"  Matches Found      : {s4_payload['matches_count']} transactions ({s4_payload['matched_rrns']})")
    print(f"  Canonical State    : {s4_state.value}")
    print(f"  Chime Guard Action : BLOCKED (Cannot assume payment without UTR)")
    print(f"  Clarifying Question: \"{s4_payload['clarifying_question']}\"")

    # -------------------------------------------------------------
    # Scenario 5: Composite Risk Escalation
    # -------------------------------------------------------------
    reset_sandbox_state()
    orchestrator = SettleOrchestrator()
    rrn5 = "556677889900"
    bank_tool.register_transaction(rrn=rrn5, amount=12000.0, status=BankStatus.SUCCESS, payer_bank="HDFC Bank")

    g5 = DisputeGrievance(
        dispute_id="DSP_SCENARIO_5",
        merchant_id="MERCH_HIGH_RISK",
        device_id="SB_DELHI_0841",
        rrn=rrn5,
        amount=12000.0,
        voice_transcript="Bada consignment payment 12000 rupaye ruka hai",
    )
    s5 = orchestrator.resolve_dispute(g5)
    print("\n[SCENARIO 5: COMPOSITE RISK ESCALATION & AUTO CASE FILE]")
    print(f"  Input: High-value order ₹{s5.amount:,.2f}")
    print(f"  Composite Risk     : {s5.risk_score:.2f} (Threshold: 0.65)")
    print(f"  Circuit Breaker    : {'TRIPPED' if s5.hitl_required else 'CLEARED'}")
    print(f"  Workflow State     : HALTED at Supervisor Desk (Completed: {s5.is_completed})")
    print(f"  Case File Dossier  : ID={s5.risk_case_file['case_id']}")
    print(f"  Recommended Action : {s5.risk_case_file['recommended_action']}")
    print(f"  1-Tap Actions      : {s5.risk_case_file['one_tap_actions']}")

    # Cryptographic Audit Chain Verification
    is_valid, err = audit_logger.verify_chain_integrity()
    print("\n" + "-" * 80)
    print(f"CRYPTOGRAPHIC AUDIT CHAIN INTEGRITY: {'VALID [VERIFIED]' if is_valid else 'FAILED'}")
    print(f"Total Audit Blocks in Chain: {len(audit_logger.entries)}")
    print(f"Latest Block Tip SHA-256   : {audit_logger.latest_hash}")
    print("=" * 80)

if __name__ == "__main__":
    run_scenarios()

