"""
SETTLE.AI - Agent Unit & Integration Test Suite
Validates the complete autonomous teammate decision pipeline across all hackathon scenarios.
"""

import pytest
from settle_ai.agent.schemas import (
    DisputeGrievance,
    DisputeChannel,
    BankStatus,
    SoundboxStatus,
    LedgerStatus,
    ResolutionAction,
)
from settle_ai.agent.orchestrator import SettleOrchestrator
from settle_ai.agent.tools import reset_sandbox_state


@pytest.fixture(autouse=True)
def clean_sandbox():
    """Resets all mock tools to initial pristine state before every test."""
    reset_sandbox_state()
    yield


@pytest.fixture
def orchestrator():
    return SettleOrchestrator()


def test_scenario_1_autonomous_settlement(orchestrator):
    """
    Scenario 1: Standard dispute (INR 350).
    Bank debited, Soundbox missed packet, Ledger uncredited.
    Expectation: Autonomous settlement in <1s, Soundbox chirp pushed, ledger credited.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_001",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn="410294820192",
        amount=350.0,
        voice_transcript="Bhaiya 350 rupaye kata par Soundbox nahi bola",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Gupta Tea Stall",
        merchant_phone="+919811223344",
    )

    final_state = orchestrator.resolve_dispute(grievance)

    # 1. Verification of Diagnostics
    assert final_state.bank_status == BankStatus.SUCCESS
    assert final_state.soundbox_status == SoundboxStatus.PACKET_DROPPED
    assert final_state.ledger_status == LedgerStatus.UNCREDITED

    # 2. Verification of Confidence & Circuit Breaker
    assert final_state.confidence_score >= 0.95, f"Expected confidence >= 95%, got {final_state.confidence_score}"
    assert final_state.hitl_required is False, "Circuit breaker should NOT trip for INR 350 high-confidence transaction"
    assert final_state.resolution_action == ResolutionAction.AUTONOMOUS_SETTLE_PUSH_SOUNDBOX

    # 3. Verification of Write Execution
    assert final_state.soundbox_pushed is True, "Soundbox chirp was not pushed"
    assert final_state.ledger_credited is True, "Merchant ledger was not credited"
    assert final_state.notification_dispatched is True, "WhatsApp notification was not dispatched"
    assert final_state.is_completed is True

    # 4. Verification of Audit Trail
    assert len(final_state.execution_steps) >= 5, "Incomplete execution audit trace"
    print("\n[SUCCESS] Scenario 1 Autonomous Settle Trace:")
    for step in final_state.execution_steps:
        clean_summary = step.summary.replace("\u20b9", "INR ")
        print(f"  -> [{step.node_name}] {step.status} ({step.latency_ms}ms): {clean_summary}")


def test_scenario_2_high_value_circuit_breaker_and_resume(orchestrator):
    """
    Scenario 2: High-value dispute (INR 15,000).
    Amount exceeds INR 5,000 safety threshold.
    Expectation: Autonomous execution pauses, compiles HITL dossier.
                 Supervisor approves -> Resumes and completes settlement.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_002_HIGH_VAL",
        merchant_id="MERCH_SHARMA_KIRANA",
        device_id="SB_DELHI_0841",
        rrn="883920194821",
        amount=15000.0,
        voice_transcript="Bade order ka 15,000 nahi aaya hai",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Sharma Kirana Store",
    )

    # 1. Run initial resolution
    state_after_halt = orchestrator.resolve_dispute(grievance)

    # Circuit breaker must trip
    assert state_after_halt.hitl_required is True, "Circuit breaker failed to trip for INR 15,000!"
    assert state_after_halt.is_completed is False, "Graph should not mark completed when halted at HITL"
    assert state_after_halt.soundbox_pushed is False, "Safety violation: Soundbox chirp dispatched without approval!"
    assert "HIGH_VALUE_THRESHOLD" in state_after_halt.hitl_reason

    clean_reason = state_after_halt.hitl_reason.replace("\u20b9", "INR ")
    print(f"\n[CIRCUIT BREAKER TRIPPED] Reason: {clean_reason}")

    # 2. Check pending list
    pending = orchestrator.list_pending_hitl()
    assert any(d.dispute_id == "DSP_TEST_002_HIGH_VAL" for d in pending)

    # 3. Simulate Human Supervisor 1-Click Sign-Off
    notes = "Reviewed HDFC switch clearing logs. Customer debited verified. Approved by L2 Lead."
    state_after_resume = orchestrator.approve_hitl(
        dispute_id="DSP_TEST_002_HIGH_VAL",
        supervisor_notes=notes,
    )

    # Verified resumed execution
    assert state_after_resume.hitl_approved is True
    assert state_after_resume.soundbox_pushed is True
    assert state_after_resume.ledger_credited is True
    assert state_after_resume.is_completed is True
    clean_msg = state_after_resume.final_resolution_message.replace("\u20b9", "INR ")
    print(f"[HITL SIGN-OFF RESUMED] Final resolution: {clean_msg}")


def test_scenario_3_bank_reversal_pending(orchestrator):
    """
    Scenario 3: Bank Switch shows REVERSAL_INITIATED (INR 420).
    Expectation: Auto provisional credit and dual notification.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_003_REV",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn="772910394812",
        amount=420.0,
        channel=DisputeChannel.WHATSAPP,
    )

    state = orchestrator.resolve_dispute(grievance)
    assert state.bank_status == BankStatus.REVERSAL_INITIATED
    assert state.confidence_score >= 0.95
    assert state.resolution_action == ResolutionAction.PROVISIONAL_CREDIT_AND_NOTIFY
    assert state.ledger_credited is True


def test_scenario_4_idempotency_protection(orchestrator):
    """
    Scenario 4: Idempotency Protection.
    Running the same dispute twice must NOT double-credit the merchant ledger.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_004_IDEMPOTENT",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn="410294820192",
        amount=350.0,
    )

    state_run_1 = orchestrator.resolve_dispute(grievance)
    initial_bal = state_run_1.ledger_record.balance_after

    # Run again with same RRN
    state_run_2 = orchestrator.resolve_dispute(grievance)
    assert state_run_2.ledger_record.balance_after == initial_bal, "Idempotency failed: Balance incremented twice!"
    print(f"\n[IDEMPOTENCY VERIFIED] Balance remained steady at INR {initial_bal:,.2f}")


def test_scenario_5_event_streaming(orchestrator):
    """
    Scenario 5: Real-time event generator streaming.
    Verifies node events emitted for WebSocket / Ops Control Room consumers.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_005_STREAM",
        merchant_id="MERCH_SHARMA_KIRANA",
        device_id="SB_DELHI_0841",
        rrn="982174019284",
        amount=500.0,
    )

    events = list(orchestrator.stream_dispute_resolution(grievance))
    assert len(events) >= 6

    node_names = [e["node_name"] for e in events if e.get("event_type") == "NODE_EXECUTED"]
    assert "node_ingest" in node_names
    assert "node_diagnose_bank" in node_names
    assert "node_diagnose_iot" in node_names
    assert "node_diagnose_ledger" in node_names
    assert "node_evaluate_risk" in node_names
    assert "node_autonomous_settle" in node_names

    terminal_event = events[-1]
    assert terminal_event["event_type"] == "WORKFLOW_COMPLETED"
    assert terminal_event["is_completed"] is True
    print("\n[STREAMING VERIFIED] Received all intermediate node events:")
    for n in node_names:
        print(f"  ~ Streamed node: {n}")


def test_scenario_6_fake_payment_paytm_spoof_shield(orchestrator):
    """
    Scenario 6: Paytm Spoof / Fake Payment Interception.
    Simulates a fraudulent customer claiming payment with an invalid RRN.
    Verifies SETU intercepts the fraud, halts ledger credit, and sounds security alarm.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_006_SPOOF",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn="FAKE99900011",
        amount=500.0,
        voice_transcript="Customer keh raha hai usne ₹500 pay kar diya screenshot dikhaya",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Gupta Tea Stall",
    )

    final_state = orchestrator.resolve_dispute(grievance)

    assert final_state.is_completed is True
    assert final_state.fraud_alert_triggered is True
    assert final_state.ledger_credited is False, "Fraudulent transaction should NEVER credit ledger!"
    assert "COUNTERFEIT PAYMENT INTERCEPTED" in final_state.final_resolution_message
    print("\n[PAYTM SPOOF SHIELD VERIFIED] Intercepted fake transaction without ledger loss.")


def test_scenario_7_proactive_sales_upgrade_evaluation(orchestrator):
    """
    Scenario 7: Measurable Sales Outcome — Proactive Hardware Upgrade Pitch.
    When a merchant with an obsolete Soundbox 2G experiences packet drops,
    SETU resolves the dispute AND autonomously attaches a Soundbox 4G Pro upgrade offer.
    """
    grievance = DisputeGrievance(
        dispute_id="DSP_TEST_007_SALES",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn="410294820192",
        amount=350.0,
        voice_transcript="Bhaiya 350 rupaye kata par Soundbox nahi bola",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Gupta Tea Stall",
    )

    final_state = orchestrator.resolve_dispute(grievance)

    assert final_state.is_completed is True
    assert final_state.ledger_credited is True
    assert final_state.sales_outcome_recorded is True
    assert final_state.sales_pitch_generated is not None
    assert "Soundbox 4G Pro" in final_state.sales_pitch_generated
    print(f"\n[SALES ENGINE VERIFIED] Generated proactive upgrade pitch: {final_state.sales_pitch_generated}")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
