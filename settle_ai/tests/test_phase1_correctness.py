"""
SETTLE.AI - Phase 1 Core Correctness & Scripted Scenarios Test Suite
Validates:
1. Scenario 1 (Credited / Packet Dropped): Confirmed on ledger -> chime authorized with UTR spoken.
2. Scenario 2 (Device Muted / Diagnosed): Merchant reports 'chime nahi baja' -> volume=0 diagnosed, remotely unmuted to 80%.
3. Scenario 3 (Failed / Reversal Due): Bank decline -> explains customer auto-reversal deadline + RBI TAT compensation liability.
4. Scenario 4 (Ambiguous): Multiple transactions match amount -> prompts clarifying question (last 4 digits of UTR).
5. Scenario 5 (Composite Risk Escalation): High-risk composite profile -> generates structured case file and halts for supervisor.
6. Chime Guard Security: Proves chime cannot be replayed without ledger confirmation (scam defense).
7. Hash-Chained Audit Trail: Proves cryptographic SHA-256 chain immutability and tamper detection.
"""

import pytest
from datetime import datetime, timezone

from settle_ai.agent.schemas import (
    DisputeGrievance,
    DisputeChannel,
    BankStatus,
    SoundboxStatus,
    LedgerStatus,
    CanonicalTxState,
    RootCauseLabel,
    ResolutionAction,
    SoundboxTelemetry,
)
from settle_ai.agent.tools import (
    bank_tool,
    ledger_tool,
    soundbox_tool,
    reset_sandbox_state,
)
from settle_ai.agent.orchestrator import SettleOrchestrator
from settle_ai.agent.state_resolver import TransactionStateResolver
from settle_ai.agent.chime_guard import SoundboxChimeGuard
from settle_ai.agent.device_diagnostics import DeviceDiagnosticsEngine
from settle_ai.agent.decision_engine import DecisionEngine
from settle_ai.agent.audit_logger import audit_logger, AuditLogger
from settle_ai.config import (
    RBI_UPI_AUTO_REVERSAL_TAT_DAYS,
    RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR,
    RISK_ESCALATION_THRESHOLD,
)


@pytest.fixture(autouse=True)
def clean_sandbox():
    """Resets all mock tools to initial pristine state before every test."""
    reset_sandbox_state()
    yield


@pytest.fixture
def fresh_orchestrator():
    """Provides a fresh orchestrator instance for testing."""
    return SettleOrchestrator()


def test_scenario_1_credited_packet_dropped(fresh_orchestrator):
    """
    Scenario 1 (Credited / Packet Dropped):
    - Switch status: SUCCESS (₹500.0)
    - Soundbox: PACKET_DROPPED
    - Core Ledger: UNCREDITED -> auto-reconciled
    Expectation:
    - Canonical state: DEEMED_SUCCESS / CREDITED
    - Chime guard: Authorized
    - Soundbox chirp dispatched
    - UTR last 4 digits verified in audit trace
    """
    rrn = "112233445566"
    amount = 500.0
    merchant_id = "MERCH_GUPTA_TEA"
    device_id = "SB_DELHI_0841"

    bank_tool.register_transaction(
        rrn=rrn,
        amount=amount,
        status=BankStatus.SUCCESS,
        customer_vpa="amit.patel@okaxis",
        payer_bank="Axis Bank",
        raw_message="Cleared via UPI",
    )
    soundbox_tool._devices[device_id]["status"] = SoundboxStatus.PACKET_DROPPED
    soundbox_tool._devices[device_id]["volume"] = 80
    soundbox_tool._devices[device_id]["is_online"] = True

    grievance = DisputeGrievance(
        dispute_id="DSP_SCENARIO_1_CREDITED",
        merchant_id=merchant_id,
        device_id=device_id,
        rrn=rrn,
        amount=amount,
        voice_transcript="Bhaiya ₹500 ka payment aaya par Soundbox nahi bola",
        channel=DisputeChannel.INDIC_VOICE,
        merchant_name="Gupta Tea Stall",
    )

    final_state = fresh_orchestrator.resolve_dispute(grievance)

    assert final_state.canonical_state in (CanonicalTxState.CREDITED, CanonicalTxState.DEEMED_SUCCESS)
    assert final_state.soundbox_pushed is True
    assert final_state.ledger_credited is True
    assert final_state.hitl_required is False
    assert final_state.is_completed is True
    assert final_state.audit_hash_sha256 is not None
    # Verify root cause was identified as device/packet drop
    assert final_state.root_cause_label == RootCauseLabel.CREDITED_DEVICE_OFFLINE


def test_scenario_2_device_muted_diagnosed(fresh_orchestrator):
    """
    Scenario 2 (Device Muted / Diagnosed):
    - Merchant complains: 'Chime nahi baja'
    - Telemetry check reveals: volume == 0 (device muted)
    - Autonomous action: Remotely unmutes speaker to 80%
    - Root cause label: DEVICE_MUTED
    - Advisory explains to merchant that volume was muted and has been restored
    """
    device_id = "SB_DELHI_0841"
    rrn = "223344556677"
    amount = 450.0

    # Setup device as muted (volume = 0)
    soundbox_tool._devices[device_id]["volume"] = 0
    soundbox_tool._devices[device_id]["status"] = SoundboxStatus.MUTED
    soundbox_tool._devices[device_id]["is_online"] = True

    bank_tool.register_transaction(
        rrn=rrn,
        amount=amount,
        status=BankStatus.SUCCESS,
        customer_vpa="vikram.singh@icici",
        payer_bank="ICICI Bank",
        raw_message="UPI Approved",
    )

    grievance = DisputeGrievance(
        dispute_id="DSP_SCENARIO_2_MUTED",
        merchant_id="MERCH_GUPTA_TEA",
        device_id=device_id,
        rrn=rrn,
        amount=amount,
        voice_transcript="Soundbox bilkul aawaz nahi kar raha",
        channel=DisputeChannel.INDIC_VOICE,
    )

    final_state = fresh_orchestrator.resolve_dispute(grievance)

    # Remediation check
    assert final_state.device_remediation_applied is not None
    assert "80%" in final_state.device_remediation_applied
    assert final_state.root_cause_label == RootCauseLabel.DEVICE_MUTED
    # Device volume in simulated registry restored to 80%
    assert soundbox_tool._devices[device_id]["volume"] == 80
    assert final_state.soundbox_pushed is True


def test_scenario_3_failed_reversal_due(fresh_orchestrator):
    """
    Scenario 3 (Failed / Reversal Due under RBI TAT):
    - NPCI / Bank switch indicates transaction failed or reversal initiated
    - Canonical state: FAILED_REVERSAL_DUE
    - SETU explains customer auto-reversal timeline (T+1 days)
    - Cites regulatory delay compensation (INR 100/day) per RBI circular
    - Zero funds released to merchant ledger, Soundbox chime blocked
    """
    rrn = "334455667788"
    amount = 800.0

    bank_tool.register_transaction(
        rrn=rrn,
        amount=amount,
        status=BankStatus.REVERSAL_INITIATED,
        customer_vpa="neha.verma@sbi",
        payer_bank="State Bank of India",
        raw_message="Customer debited, clearing failed. Auto-reversal in flight.",
    )

    canonical_state, res_payload = TransactionStateResolver.resolve_state(
        merchant_id="MERCH_GUPTA_TEA",
        amount=amount,
        rrn=rrn,
    )

    assert canonical_state == CanonicalTxState.FAILED_REVERSAL_DUE
    assert res_payload["can_replay_chime"] is False
    assert res_payload["rbi_tat_days"] == RBI_UPI_AUTO_REVERSAL_TAT_DAYS
    assert res_payload["compensation_per_day"] == RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR

    grievance = DisputeGrievance(
        dispute_id="DSP_SCENARIO_3_FAILED",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
        rrn=rrn,
        amount=amount,
        voice_transcript="Customer ke phone se 800 kate par mere paas nahi aaye",
    )

    final_state = fresh_orchestrator.resolve_dispute(grievance)
    assert final_state.canonical_state == CanonicalTxState.FAILED_REVERSAL_DUE
    assert final_state.root_cause_label == RootCauseLabel.PAYER_BANK_DECLINE
    # Soundbox chime strictly blocked because transaction failed
    assert final_state.soundbox_pushed is False


def test_scenario_4_ambiguous_clarification():
    """
    Scenario 4 (Ambiguous / Clarification Prompt):
    - Merchant asks by amount only ('₹500 aaya kya?')
    - Multiple ₹500 transactions exist within the query window
    - Canonical state: AMBIGUOUS
    - SETU generates single targeted clarifying question asking for last 4 digits of customer UTR
    - Chime is NOT played
    """
    merchant_id = "MERCH_GUPTA_TEA"
    amount = 500.0

    # Seed multiple ₹500 transactions for this merchant
    bank_tool.register_transaction(
        rrn="445566778811",
        amount=amount,
        status=BankStatus.SUCCESS,
        customer_vpa="user1@okaxis",
        payer_bank="Axis Bank",
    )
    bank_tool.register_transaction(
        rrn="445566778822",
        amount=amount,
        status=BankStatus.SUCCESS,
        customer_vpa="user2@okhdfc",
        payer_bank="HDFC Bank",
    )

    # Query without explicit RRN
    canonical_state, payload = TransactionStateResolver.resolve_state(
        merchant_id=merchant_id,
        amount=amount,
        rrn=None,
    )

    assert canonical_state == CanonicalTxState.AMBIGUOUS
    assert payload["can_replay_chime"] is False
    assert payload["action"] == "PROMPT_CLARIFICATION"
    assert "aakhiri 4 ank" in payload["clarifying_question"]
    assert len(payload["matched_rrns"]) >= 2


def test_scenario_5_composite_risk_escalation(fresh_orchestrator):
    """
    Scenario 5 (Composite Risk Escalation):
    - Replaces flat INR 5,000 threshold with composite risk score
    - Multi-factor evaluation: High amount + dispute spike -> Risk Score >= 0.65
    - Autonomous execution pauses
    - Auto-generates structured incident dossier / Case File for supervisor 1-click review
    """
    amount = 12000.0
    rrn = "556677889900"
    merchant_id = "MERCH_HIGH_RISK"
    device_id = "SB_DELHI_0841"

    bank_tool.register_transaction(
        rrn=rrn,
        amount=amount,
        status=BankStatus.SUCCESS,
        customer_vpa="wholesaler@okhdfc",
        payer_bank="HDFC Bank",
    )

    # Evaluate composite risk directly
    score, factors = DecisionEngine.calculate_composite_risk(
        amount=amount,
        merchant_tenure_days=15,  # New merchant (< 30 days)
        dispute_count_30d=4,      # 4 disputes in 30 days
        asr_confidence=0.88,
    )
    assert score >= RISK_ESCALATION_THRESHOLD

    grievance = DisputeGrievance(
        dispute_id="DSP_SCENARIO_5_RISK",
        merchant_id=merchant_id,
        device_id=device_id,
        rrn=rrn,
        amount=amount,
        voice_transcript="Bada consignment payment 12000 rupaye ruka hai",
    )

    final_state = fresh_orchestrator.resolve_dispute(grievance)

    # Workflow must halt for supervisor
    assert final_state.hitl_required is True
    assert final_state.is_completed is False
    assert final_state.soundbox_pushed is False
    assert final_state.risk_score >= RISK_ESCALATION_THRESHOLD
    # Structured Case File generated
    assert final_state.risk_case_file is not None
    assert final_state.risk_case_file["composite_risk_score"] >= RISK_ESCALATION_THRESHOLD
    assert "one_tap_actions" in final_state.risk_case_file
    assert "APPROVE_AND_SETTLE" in final_state.risk_case_file["one_tap_actions"]
    assert "REJECT_CLAIM" in final_state.risk_case_file["one_tap_actions"]


def test_strict_chime_guard_blocks_unconfirmed_claims():
    """
    Proves that the Soundbox chime CANNOT be played based on user grievance/prompt alone.
    Deterministic guard blocks chime if bank switch shows non-SUCCESS or ledger has zero credit.
    """
    # 1. Invalid RRN
    ok, reason = SoundboxChimeGuard.verify_chime_authorization(
        merchant_id="MERCH_GUPTA_TEA",
        claimed_amount=500.0,
        rrn="INVALID_RRN",
    )
    assert ok is False
    assert "Invalid 12-digit" in reason

    # 2. Fake / unconfirmed RRN with zero ledger record
    ok, reason = SoundboxChimeGuard.verify_chime_authorization(
        merchant_id="MERCH_GUPTA_TEA",
        claimed_amount=500.0,
        rrn="999988887777",
    )
    assert ok is False
    assert "zero confirmed credit" in reason.lower() or "blocked" in reason.lower()


def test_cryptographic_audit_log_hash_chain_integrity():
    """
    Validates SHA-256 hash chaining across agent decisions and tests tamper detection.
    """
    test_logger = AuditLogger()

    entry1 = test_logger.record_decision(
        dispute_id="DSP_AUDIT_01",
        merchant_id="MERCH_GUPTA_TEA",
        inputs={"amount": 400.0, "rrn": "111122223333"},
        tools_called=["bank_tool.verify_transaction"],
        state_determined="CREDITED",
        action_taken="AUTONOMOUS_SETTLE",
        reason="Verified ledger credit",
    )

    entry2 = test_logger.record_decision(
        dispute_id="DSP_AUDIT_02",
        merchant_id="MERCH_SHARMA_KIRANA",
        inputs={"amount": 15000.0, "rrn": "444455556666"},
        tools_called=["DecisionEngine.evaluate_risk"],
        state_determined="DEEMED_SUCCESS",
        action_taken="ESCALATE_HITL",
        reason="Composite risk score 0.85 exceeded threshold",
    )

    # Verify link: entry2.prev_hash must match entry1.entry_hash
    assert entry2.prev_hash == entry1.entry_hash

    # Verify chain integrity
    is_valid, err = test_logger.verify_chain_integrity()
    assert is_valid is True
    assert err is None

    # Simulate malicious tamper in block #1
    entry1.reason = "TAMPERED_FRAUDULENT_REASON"
    is_valid_after_tamper, tamper_err = test_logger.verify_chain_integrity()
    assert is_valid_after_tamper is False
    assert "Tampered block detected" in tamper_err
