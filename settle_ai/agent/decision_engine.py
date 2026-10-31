"""
SETTLE.AI - Deterministic Risk Evaluator & Decision Engine
Evaluates cross-system telemetry, computes mathematically grounded confidence scores,
and enforces safety circuit breakers (₹5,000 cap & 95% confidence rule).
"""

import logging
from typing import Tuple, Optional
from settle_ai.agent.schemas import (
    BankStatus,
    SoundboxStatus,
    LedgerStatus,
    ResolutionAction,
)

logger = logging.getLogger("settle_ai.decision_engine")

# Strict Paytm Operations Risk Thresholds
MAX_AUTONOMOUS_VALUE_INR = 5000.0
MIN_AUTONOMOUS_CONFIDENCE = 0.95


class DecisionEngine:
    """Evaluates cross-system state consistency and risk boundaries."""

    @staticmethod
    def calculate_confidence(
        bank_status: BankStatus,
        soundbox_status: SoundboxStatus,
        ledger_status: LedgerStatus,
        amount: float,
        claimed_amount: float,
    ) -> Tuple[float, str]:
        """
        Calculates cross-system consistency confidence score [0.0 - 1.0].
        Returns (confidence_score, diagnostic_summary).
        """
        # Amount mismatch penalty
        if abs(amount - claimed_amount) > 1.0:
            return 0.20, f"Amount discrepancy: Switch shows ₹{amount}, but grievance claimed ₹{claimed_amount}."

        # Scenario 1: Bank Cleared, Device Missed Packet, Ledger Uncredited (Classic Soundbox Drop)
        if bank_status == BankStatus.SUCCESS and soundbox_status in (
            SoundboxStatus.PACKET_DROPPED,
            SoundboxStatus.OFFLINE,
            SoundboxStatus.MUTED,
            SoundboxStatus.ONLINE,
            SoundboxStatus.ACK_RECEIVED,
        ) and ledger_status in (LedgerStatus.UNCREDITED, LedgerStatus.PROVISIONAL_CREDITED):
            return 0.98, "Strong corroboration: Bank switch debited, Soundbox missed MQTT ACK, ledger uncredited."

        # Scenario 2: Auto-reversal in flight at banking switch
        if bank_status == BankStatus.REVERSAL_INITIATED:
            return 0.95, "Banking switch indicates customer auto-reversal is pending clearing."

        # Scenario 3: Bank failed or not found (Customer was never debited)
        if bank_status in (BankStatus.FAILED, BankStatus.NOT_FOUND):
            return 0.15, f"Bank switch indicates transaction failed ({bank_status.value}). Customer account was not charged."

        # Scenario 4: Already settled and played
        if bank_status == BankStatus.SUCCESS and soundbox_status == SoundboxStatus.ACK_RECEIVED and ledger_status == LedgerStatus.SETTLED:
            return 0.99, "Transaction already reconciled, credited, and Soundbox chirp played."

        # Scenario 5: Bank debited, Soundbox online, ledger credited, but merchant still raised ticket
        if bank_status == BankStatus.SUCCESS and ledger_status in (LedgerStatus.SETTLED, LedgerStatus.PROVISIONAL_CREDITED):
            return 0.96, "Payment cleared and merchant account credited. Soundbox chirp re-push required."

        # Default fallback for ambiguous edge cases
        return 0.60, f"Ambiguous system states: Bank={bank_status}, Soundbox={soundbox_status}, Ledger={ledger_status}."

    @staticmethod
    def evaluate_risk(
        amount: float,
        confidence_score: float,
        bank_status: BankStatus,
        soundbox_status: SoundboxStatus,
    ) -> Tuple[bool, Optional[str], ResolutionAction]:
        """
        Applies Paytm Autonomous Teammate safety circuit breakers:
        - Value >= ₹5,000 -> Force Human-in-the-Loop escalation
        - Confidence < 95% -> Force Human-in-the-Loop escalation
        - Otherwise -> Execute Autonomous Settlement
        """
        logger.info(f"[DecisionEngine] Evaluating risk for Amount=₹{amount}, Confidence={confidence_score:.2f}")

        # Rule 1: High-Value Circuit Breaker
        if amount >= MAX_AUTONOMOUS_VALUE_INR:
            reason = (
                f"HIGH_VALUE_THRESHOLD: Transaction amount ₹{amount:,.2f} exceeds "
                f"autonomous safety limit of ₹{MAX_AUTONOMOUS_VALUE_INR:,.2f}. Escalating for supervisor 1-click sign-off."
            )
            return True, reason, ResolutionAction.ESCALATE_HITL

        # Rule 2: Confidence Circuit Breaker
        if confidence_score < MIN_AUTONOMOUS_CONFIDENCE:
            reason = (
                f"LOW_CONFIDENCE_BREAKER: Confidence score of {confidence_score:.1%} is below "
                f"the required {MIN_AUTONOMOUS_CONFIDENCE:.0%} threshold. Potential anomaly detected."
            )
            return True, reason, ResolutionAction.ESCALATE_HITL

        # Rule 3: Reversal Handling
        if bank_status == BankStatus.REVERSAL_INITIATED:
            return False, None, ResolutionAction.PROVISIONAL_CREDIT_AND_NOTIFY

        # Rule 4: Standard Autonomous Settlement
        if bank_status == BankStatus.SUCCESS:
            return False, None, ResolutionAction.AUTONOMOUS_SETTLE_PUSH_SOUNDBOX

        # Default fallback
        return True, "Default safety halt: Unmapped state combination.", ResolutionAction.ESCALATE_HITL
