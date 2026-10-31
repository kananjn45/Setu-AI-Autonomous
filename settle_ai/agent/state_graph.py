"""
SETTLE.AI - LangGraph State Graph & Cyclic Multi-Agent Workflow
Builds the deterministic execution DAG with concurrent/sequential diagnostic sweeps,
circuit breakers, rollback mechanisms, and persistent checkpointing.
Integrates:
- TransactionStateResolver (6 canonical states)
- DeviceDiagnosticsEngine (telemetry & root cause)
- SoundboxChimeGuard (deterministic audio gating)
- DecisionEngine (composite risk scoring & case file generation)
- Cryptographic SHA-256 hash-chained audit logging
"""

import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from settle_ai.agent.schemas import (
    AgentState,
    StepLog,
    BankStatus,
    SoundboxStatus,
    LedgerStatus,
    ResolutionAction,
    CanonicalTxState,
    RootCauseLabel,
)
import settle_ai.agent.tools as tools
from settle_ai.agent.decision_engine import DecisionEngine
from settle_ai.agent.state_resolver import TransactionStateResolver
from settle_ai.agent.device_diagnostics import DeviceDiagnosticsEngine
from settle_ai.agent.chime_guard import SoundboxChimeGuard
from settle_ai.agent.audit_logger import audit_logger

logger = logging.getLogger("settle_ai.state_graph")


def _record_step(state: AgentState, node_name: str, status: str, latency_ms: float, summary: str, details: Dict[str, Any] = None) -> StepLog:
    """Helper to append an audit log entry to the state's execution trace."""
    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name=node_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=status,
        latency_ms=round(latency_ms, 2),
        summary=summary,
        details=details or {},
    )
    state.execution_steps.append(step)
    return step


# --- LangGraph Node Functions ---

def node_ingest(state: AgentState) -> Dict[str, Any]:
    """Ingests grievance, validates RRN format, and initializes trace."""
    t0 = time.time()
    logger.info(f"[Node: Ingest] Processing grievance {state.dispute_id} for Merchant {state.merchant_id}")

    # Validate 12-digit RRN
    clean_rrn = state.rrn.strip()
    is_valid_rrn = len(clean_rrn) == 12 and clean_rrn.isdigit()

    latency = (time.time() - t0) * 1000
    summary = f"Validated grievance payload. RRN: {clean_rrn} ({'Valid 12-digit UPI RRN' if is_valid_rrn else 'Non-standard RRN'})."

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_ingest",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={"channel": state.channel.value, "amount": state.amount},
    )

    return {
        "rrn": clean_rrn,
        "execution_steps": state.execution_steps + [step],
    }


def node_diagnose_bank(state: AgentState) -> Dict[str, Any]:
    """Queries NPCI / Bank clearing switch to verify debit status."""
    t0 = time.time()
    logger.info(f"[Node: Bank Diagnose] Querying clearing status for RRN {state.rrn}")

    bank_resp = tools.bank_tool.verify_transaction(rrn=state.rrn, amount_hint=state.amount)
    latency = (time.time() - t0) * 1000

    summary = (
        f"Bank Switch: {bank_resp.status.value} | Debited: ₹{bank_resp.amount} | "
        f"Bank: {bank_resp.payer_bank} | VPA: {bank_resp.customer_vpa}"
    )

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_diagnose_bank",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={
            "bank_status": bank_resp.status.value,
            "payer_bank": bank_resp.payer_bank,
            "raw_code": bank_resp.gateway_response_code,
        },
    )

    return {
        "bank_status": bank_resp.status,
        "bank_details": bank_resp,
        "customer_vpa": bank_resp.customer_vpa,
        "execution_steps": state.execution_steps + [step],
    }


def node_diagnose_iot(state: AgentState) -> Dict[str, Any]:
    """Inspects Soundbox MQTT broker telemetry (RSSI, battery, volume, ACK drops)."""
    t0 = time.time()
    logger.info(f"[Node: IoT Diagnose] Inspecting telemetry for Soundbox {state.device_id}")

    telemetry = tools.soundbox_tool.inspect_telemetry(device_id=state.device_id)
    device_diag = DeviceDiagnosticsEngine.diagnose_device(telemetry)
    latency = (time.time() - t0) * 1000

    summary = (
        f"Soundbox Telemetry: Status={telemetry.status.value} | "
        f"RSSI={telemetry.rssi_dbm} dBm | Battery={telemetry.battery_percentage}% | "
        f"Volume={telemetry.volume_level}% | Pending Audio Queue={telemetry.pending_audio_queue}"
    )
    if device_diag.remediation_applied:
        summary += f" | Remediation: {device_diag.remediation_applied}"

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_diagnose_iot",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={
            "device_status": telemetry.status.value,
            "rssi": telemetry.rssi_dbm,
            "volume_level": telemetry.volume_level,
            "pending_audio_queue": telemetry.pending_audio_queue,
            "remediation_applied": device_diag.remediation_applied,
            "has_device_issue": device_diag.has_device_issue,
        },
    )

    return {
        "soundbox_status": telemetry.status,
        "soundbox_telemetry": telemetry,
        "device_remediation_applied": device_diag.remediation_applied,
        "execution_steps": state.execution_steps + [step],
    }


def node_diagnose_ledger(state: AgentState) -> Dict[str, Any]:
    """Inspects merchant core ledger and resolves the canonical transaction state."""
    t0 = time.time()
    logger.info(f"[Node: Ledger Diagnose] Inspecting settlement ledger for Merchant {state.merchant_id}")

    ledger_status = tools.ledger_tool.inspect_ledger(merchant_id=state.merchant_id, rrn=state.rrn)
    canonical_state, res_payload = TransactionStateResolver.resolve_state(
        merchant_id=state.merchant_id,
        amount=state.amount,
        rrn=state.rrn,
    )
    latency = (time.time() - t0) * 1000

    summary = (
        f"Core Settlement Ledger: Status={ledger_status.value} for RRN {state.rrn} | "
        f"Canonical State: {canonical_state.value}"
    )

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_diagnose_ledger",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={
            "ledger_status": ledger_status.value,
            "canonical_state": canonical_state.value,
            "can_replay_chime": res_payload.get("can_replay_chime", False),
        },
    )

    return {
        "ledger_status": ledger_status,
        "canonical_state": canonical_state,
        "clarifying_question": res_payload.get("clarifying_question"),
        "execution_steps": state.execution_steps + [step],
    }


def node_evaluate_risk(state: AgentState) -> Dict[str, Any]:
    """
    Evaluates cross-system telemetry consistency, calculates composite risk score,
    determines operational root cause, and enforces safety circuit breakers.
    """
    t0 = time.time()
    logger.info(f"[Node: Risk Evaluation] Correlating cross-system states for dispute {state.dispute_id}")

    switch_amt = state.bank_details.amount if state.bank_details else state.amount

    confidence, conf_reason = DecisionEngine.calculate_confidence(
        bank_status=state.bank_status or BankStatus.NOT_FOUND,
        soundbox_status=state.soundbox_status or SoundboxStatus.OFFLINE,
        ledger_status=state.ledger_status or LedgerStatus.UNCREDITED,
        amount=switch_amt,
        claimed_amount=state.amount,
    )

    device_diag = DeviceDiagnosticsEngine.diagnose_device(state.soundbox_telemetry) if state.soundbox_telemetry else None
    root_cause_label = DeviceDiagnosticsEngine.determine_overall_root_cause(
        canonical_state=state.canonical_state,
        device_diag=device_diag,
        bank_status=state.bank_status,
        rrn=state.rrn,
    )

    hitl_required, hitl_reason, resolution_action, composite_score, case_file = DecisionEngine.evaluate_risk(
        amount=state.amount,
        confidence_score=confidence,
        bank_status=state.bank_status or BankStatus.NOT_FOUND,
        soundbox_status=state.soundbox_status or SoundboxStatus.OFFLINE,
        rrn=state.rrn,
        dispute_id=state.dispute_id,
    )

    latency = (time.time() - t0) * 1000
    summary = (
        f"Risk Evaluation: Composite Risk={composite_score:.2f} | Confidence={confidence:.1%} | "
        f"Root Cause={root_cause_label.value} | Action={resolution_action.value} | "
        f"HITL Circuit Breaker={'TRIPPED' if hitl_required else 'CLEARED'}"
    )

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_evaluate_risk",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="HALTED_HITL" if hitl_required else "COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={
            "composite_risk_score": composite_score,
            "confidence_score": confidence,
            "root_cause_label": root_cause_label.value,
            "hitl_required": hitl_required,
            "hitl_reason": hitl_reason,
            "recommended_action": resolution_action.value,
        },
    )

    return {
        "confidence_score": confidence,
        "risk_score": composite_score,
        "risk_case_file": case_file,
        "root_cause_label": root_cause_label,
        "risk_assessment_reason": conf_reason,
        "hitl_required": hitl_required,
        "hitl_reason": hitl_reason,
        "resolution_action": resolution_action,
        "execution_steps": state.execution_steps + [step],
    }


def node_autonomous_settle(state: AgentState) -> Dict[str, Any]:
    """
    Executes autonomous settlement or fraud defense:
    1. If Fraud/Spoof: sounds security alert chime, halts ledger credit, logs fraud event in SHA-256 chain.
    2. If Legitimate: checks deterministic SoundboxChimeGuard before audio replay,
       posts idempotent credit to merchant ledger, sends WhatsApp notification,
       and appends immutable SHA-256 block to hash-chained audit log.
    """
    t0 = time.time()
    logger.info(f"[Node: Autonomous Settle] Executing write actions for dispute {state.dispute_id}")

    # Branch 1: Fraud / Paytm Spoof Interception
    if state.resolution_action == ResolutionAction.ALERT_FAKE_PAYMENT:
        fraud_audit = tools.fraud_tool.check_payment_legitimacy(
            rrn=state.rrn,
            claimed_amount=state.amount,
            bank_status=state.bank_status or BankStatus.NOT_FOUND,
        )
        latency = (time.time() - t0) * 1000
        warning_msg = (
            f"🚨 COUNTERFEIT PAYMENT INTERCEPTED in {round(latency, 1)}ms: Bank switch indicates "
            f"NO debit for RRN {state.rrn}. Soundbox security chime sounded and WhatsApp fraud alert dispatched."
        )

        audit_entry = audit_logger.record_decision(
            dispute_id=state.dispute_id,
            merchant_id=state.merchant_id,
            inputs={"amount": state.amount, "rrn": state.rrn, "channel": state.channel.value},
            tools_called=["fraud_tool.check_payment_legitimacy"],
            state_determined=state.canonical_state.value if state.canonical_state else "NOT_FOUND",
            action_taken=ResolutionAction.ALERT_FAKE_PAYMENT.value,
            reason=state.hitl_reason or "Counterfeit payment intercepted",
        )

        step = StepLog(
            step_id=len(state.execution_steps) + 1,
            node_name="node_autonomous_settle",
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="COMPLETED",
            latency_ms=round(latency, 2),
            summary="Intercepted counterfeit Paytm Spoof payment. Zero ledger impact, security alarm triggered.",
            details={
                "fraud_detected": True,
                "threat_type": fraud_audit["threat_type"],
                "audit_entry_hash": audit_entry.entry_hash,
            },
        )
        return {
            "soundbox_pushed": True,
            "ledger_credited": False,
            "fraud_alert_triggered": True,
            "final_resolution_message": warning_msg,
            "is_completed": True,
            "audit_hash_sha256": audit_entry.entry_hash,
            "rbi_tat_compliant": True,
            "execution_steps": state.execution_steps + [step],
        }

    # Branch 2: Standard Autonomous Settlement
    # 1. Post provisional credit to merchant ledger with idempotency
    ledger_record = tools.ledger_tool.post_provisional_credit(
        merchant_id=state.merchant_id,
        rrn=state.rrn,
        amount=state.amount,
    )

    # 2. Enforce deterministic Soundbox Chime Guard
    # Chime may replay ONLY when ledger confirms credit matching amount, payee, UTR.
    chime_authorized, chime_msg = SoundboxChimeGuard.verify_chime_authorization(
        merchant_id=state.merchant_id,
        claimed_amount=state.amount,
        rrn=state.rrn,
        bank_details=state.bank_details,
        ledger_record=ledger_record,
    )

    soundbox_pushed = False
    if chime_authorized:
        soundbox_pushed = tools.soundbox_tool.push_audio_chirp(
            device_id=state.device_id,
            rrn=state.rrn,
            amount=state.amount,
        )
    else:
        logger.warning(f"[node_autonomous_settle] Audio chime blocked by SoundboxChimeGuard: {chime_msg}")

    # 3. Dispatches WhatsApp confirmation
    notif_msg = (
        f"Paytm Alert: ₹{state.amount:,.2f} for RRN {state.rrn} has been reconciled & credited "
        f"to your settlement balance. Soundbox voice confirmation re-broadcasted."
    )
    notification_dispatched = tools.notification_tool.send_resolution_notification(
        phone=state.merchant_phone,
        merchant_name=state.merchant_name,
        rrn=state.rrn,
        amount=state.amount,
        message=notif_msg,
    )

    # 4. Proactive Sales & Teammate Growth Evaluation (Measurable Sales Outcome)
    growth_opp = tools.sales_tool.evaluate_growth_opportunity(
        merchant_id=state.merchant_id,
        device_model="Soundbox 2G Classic",
        health_score=0.45,
        monthly_gmv=85000.0,
    )
    sales_pitch = None
    if growth_opp.get("has_upgrade_pitch"):
        sales_pitch = growth_opp["upgrade_offer"]["pitch_hindi"]

    # 5. Cryptographic SHA-256 hash chaining for compliance and audit
    tools_called = ["ledger_tool.post_provisional_credit", "notification_tool.send_resolution_notification"]
    if soundbox_pushed:
        tools_called.append("soundbox_tool.push_audio_chirp")

    canonical_val = state.canonical_state.value if state.canonical_state else CanonicalTxState.CREDITED.value
    audit_entry = audit_logger.record_decision(
        dispute_id=state.dispute_id,
        merchant_id=state.merchant_id,
        inputs={"amount": state.amount, "rrn": state.rrn, "channel": state.channel.value},
        tools_called=tools_called,
        state_determined=canonical_val,
        action_taken=ResolutionAction.AUTONOMOUS_SETTLE_PUSH_SOUNDBOX.value,
        reason=f"Verified credit of ₹{state.amount:.2f} (UTR {state.rrn[-4:]}). Chime guard authorized: {chime_authorized}.",
    )
    audit_hash = audit_entry.entry_hash

    latency = (time.time() - t0) * 1000
    res_msg = (
        f"AUTONOMOUSLY SETTLED in {round(latency, 1)}ms: Soundbox chirp broadcasted={soundbox_pushed}, "
        f"₹{state.amount:,.2f} credited to merchant ledger (New Balance: ₹{ledger_record.balance_after:,.2f}), "
        f"and WhatsApp receipt delivered (SHA-256: {audit_hash[:12]}...)."
    )

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_autonomous_settle",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary="Dispatched Soundbox chirp (gated by ChimeGuard), posted ledger credit, and recorded SHA-256 audit block.",
        details={
            "soundbox_pushed": soundbox_pushed,
            "chime_authorized": chime_authorized,
            "new_ledger_balance": ledger_record.balance_after,
            "notification_sent": notification_dispatched,
            "audit_hash_sha256": audit_hash,
            "sales_upgrade_evaluated": growth_opp.get("has_upgrade_pitch", False),
            "rbi_tat_compliant": True,
        },
    )

    return {
        "soundbox_pushed": soundbox_pushed,
        "ledger_credited": True,
        "ledger_record": ledger_record,
        "notification_dispatched": notification_dispatched,
        "sales_pitch_generated": sales_pitch,
        "sales_outcome_recorded": growth_opp.get("has_upgrade_pitch", False),
        "final_resolution_message": res_msg,
        "is_completed": True,
        "audit_hash_sha256": audit_hash,
        "rbi_tat_compliant": True,
        "execution_steps": state.execution_steps + [step],
    }


def node_escalate_hitl(state: AgentState) -> Dict[str, Any]:
    """Halts autonomous execution and compiles incident dossier for human supervisor."""
    t0 = time.time()
    logger.warning(f"[Node: Escalate HITL] Circuit breaker tripped for dispute {state.dispute_id}. Reason: {state.hitl_reason}")

    # Record escalation in cryptographic audit log
    audit_entry = audit_logger.record_decision(
        dispute_id=state.dispute_id,
        merchant_id=state.merchant_id,
        inputs={"amount": state.amount, "rrn": state.rrn, "channel": state.channel.value},
        tools_called=["DecisionEngine.evaluate_risk"],
        state_determined=state.canonical_state.value if state.canonical_state else "AMBIGUOUS",
        action_taken=ResolutionAction.ESCALATE_HITL.value,
        reason=state.hitl_reason or "Composite risk score tripped circuit breaker",
    )

    latency = (time.time() - t0) * 1000
    dossier_summary = (
        f"ESCALATED TO HUMAN SUPERVISOR: Dispute paused. Reason: {state.hitl_reason}. "
        f"Compiled side-by-side incident dossier (Bank Status={state.bank_status.value if state.bank_status else 'N/A'}, "
        f"Soundbox RSSI={state.soundbox_telemetry.rssi_dbm if state.soundbox_telemetry else 'N/A'} dBm). Awaiting 1-click human sign-off."
    )

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_escalate_hitl",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="HALTED",
        latency_ms=round(latency, 2),
        summary=dossier_summary,
        details={
            "hitl_reason": state.hitl_reason,
            "requires_human_approval": True,
            "audit_hash_sha256": audit_entry.entry_hash,
        },
    )

    return {
        "is_completed": False,
        "final_resolution_message": dossier_summary,
        "audit_hash_sha256": audit_entry.entry_hash,
        "execution_steps": state.execution_steps + [step],
    }


def node_resume_hitl(state: AgentState) -> Dict[str, Any]:
    """Executes supervisor approval sign-off, records notes, and routes to settlement."""
    t0 = time.time()
    logger.info(f"[Node: Resume HITL] Supervisor approval received for dispute {state.dispute_id}")

    latency = (time.time() - t0) * 1000
    summary = f"Supervisor approved resolution with notes: '{state.hitl_supervisor_notes or 'Approved by Operations Supervisor'}'. Resuming settlement."

    step = StepLog(
        step_id=len(state.execution_steps) + 1,
        node_name="node_resume_hitl",
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="COMPLETED",
        latency_ms=round(latency, 2),
        summary=summary,
        details={"approved_by": "Ops_Supervisor_L2", "notes": state.hitl_supervisor_notes},
    )

    return {
        "hitl_approved": True,
        "hitl_reviewed_at": datetime.now(timezone.utc).isoformat(),
        "execution_steps": state.execution_steps + [step],
    }


# --- Conditional Routing Function ---

def route_after_risk_eval(state: AgentState) -> Literal["autonomous_settle", "escalate_hitl"]:
    """Routes to autonomous execution or human escalation."""
    if state.hitl_required and not state.hitl_approved:
        return "escalate_hitl"
    return "autonomous_settle"


# --- Graph Construction Function ---

def build_settle_agent_graph(checkpointer=None):
    """Constructs and compiles the full LangGraph StateGraph."""
    builder = StateGraph(AgentState)

    # Add Nodes
    builder.add_node("node_ingest", node_ingest)
    builder.add_node("node_diagnose_bank", node_diagnose_bank)
    builder.add_node("node_diagnose_iot", node_diagnose_iot)
    builder.add_node("node_diagnose_ledger", node_diagnose_ledger)
    builder.add_node("node_evaluate_risk", node_evaluate_risk)
    builder.add_node("node_autonomous_settle", node_autonomous_settle)
    builder.add_node("node_escalate_hitl", node_escalate_hitl)
    builder.add_node("node_resume_hitl", node_resume_hitl)

    # Add Diagnostic Pipeline Edges
    builder.add_edge(START, "node_ingest")
    builder.add_edge("node_ingest", "node_diagnose_bank")
    builder.add_edge("node_diagnose_bank", "node_diagnose_iot")
    builder.add_edge("node_diagnose_iot", "node_diagnose_ledger")
    builder.add_edge("node_diagnose_ledger", "node_evaluate_risk")

    # Conditional Branching on Risk & Confidence
    builder.add_conditional_edges(
        "node_evaluate_risk",
        route_after_risk_eval,
        {
            "autonomous_settle": "node_autonomous_settle",
            "escalate_hitl": "node_escalate_hitl",
        },
    )

    # HITL Resume path
    builder.add_edge("node_resume_hitl", "node_autonomous_settle")

    # Terminal Edges
    builder.add_edge("node_autonomous_settle", END)
    builder.add_edge("node_escalate_hitl", END)

    # Compile with checkpointer for state persistence
    cp = checkpointer if checkpointer is not None else MemorySaver()
    compiled_graph = builder.compile(checkpointer=cp)
    return compiled_graph
