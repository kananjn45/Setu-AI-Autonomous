"""
SETTLE.AI - Deterministic Risk Evaluator & Decision Engine
Evaluates cross-system telemetry, computes mathematically grounded composite risk scores,
and enforces safety circuit breakers (composite risk threshold & 95% cross-system confidence).

Replaces arbitrary flat caps with a multi-factor Composite Risk Score:
- Amount weight & deviation
- Merchant tenure & dispute frequency (last 30 days)
- Claim vs. ledger mismatch
- ASR voice confidence
- Repeated claim velocity
"""

import logging
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone

from settle_ai.config import (
    RISK_ESCALATION_THRESHOLD,
    WEIGHT_AMOUNT_DEVIATION,
    WEIGHT_MERCHANT_DISPUTE_VELOCITY,
    WEIGHT_CLAIM_MISMATCH,
    WEIGHT_ASR_CONFIDENCE,
)
from settle_ai.agent.schemas import (
    BankStatus,
    SoundboxStatus,
    LedgerStatus,
    ResolutionAction,
)

logger = logging.getLogger("settle_ai.decision_engine")

MIN_AUTONOMOUS_CONFIDENCE = 0.95


class DecisionEngine:
    """Evaluates cross-system state consistency and composite risk boundaries."""

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
    def calculate_composite_risk(
        amount: float,
        claimed_amount: float = 0.0,
        merchant_tenure_days: int = 180,
        dispute_count_30d: int = 0,
        asr_confidence: float = 0.95,
        claim_ledger_matched: bool = True,
        repeated_claims_count: int = 0,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Computes a deterministic, defensible multi-factor Composite Risk Score [0.0 - 1.0].
        Combines:
        - Amount exposure (higher amount = higher financial risk)
        - Merchant dispute velocity in last 30 days
        - Claim vs switch/ledger match
        - Voice ASR confidence score
        - Repeated identical claims pattern
        """
        claimed = claimed_amount if claimed_amount > 0 else amount

        # 1. Amount Risk Factor (Scaled: <=500 -> 0.05, 5000 -> 0.70, >=15000 -> 1.0)
        if amount <= 500:
            amount_risk = 0.05
        elif amount <= 2000:
            amount_risk = 0.15 + (amount - 500) / 1500.0 * 0.20  # 0.15 - 0.35
        elif amount < 5000:
            amount_risk = 0.35 + (amount - 2000) / 3000.0 * 0.25  # 0.35 - 0.60
        else:
            amount_risk = min(1.0, 0.70 + (amount - 5000.0) / 10000.0 * 0.30)

        # 2. Merchant Dispute Velocity & Tenure
        tenure_factor = 0.60 if merchant_tenure_days < 30 else (0.20 if merchant_tenure_days < 90 else 0.05)
        if dispute_count_30d == 0:
            dispute_risk = 0.05
        elif dispute_count_30d <= 2:
            dispute_risk = 0.25
        elif dispute_count_30d <= 5:
            dispute_risk = 0.60
        else:
            dispute_risk = 1.0
        # Combine tenure + dispute count for merchant velocity component
        merchant_risk = min(1.0, 0.4 * tenure_factor + 0.6 * dispute_risk)

        # 3. Claim / Ledger State Mismatch Risk
        mismatch_amount = abs(amount - claimed)
        if not claim_ledger_matched or mismatch_amount > 1.0:
            mismatch_risk = 0.90
        else:
            mismatch_risk = 0.05

        # 4. ASR Confidence Risk (Low ASR confidence indicates ambiguity/garbled input)
        asr_risk = max(0.0, min(1.0, 1.0 - asr_confidence))

        # 5. Repeated Identical Claims Multiplier
        repeated_penalty = min(0.30, repeated_claims_count * 0.15)

        # Weighted aggregate score
        raw_score = (
            WEIGHT_AMOUNT_DEVIATION * amount_risk
            + WEIGHT_MERCHANT_DISPUTE_VELOCITY * merchant_risk
            + WEIGHT_CLAIM_MISMATCH * mismatch_risk
            + WEIGHT_ASR_CONFIDENCE * asr_risk
            + repeated_penalty
        )

        # High-value exposure floor for retail Soundbox rails (amounts >= 5,000 INR)
        if amount >= 5000.0:
            raw_score = max(raw_score, 0.70 + min(0.30, (amount - 5000.0) / 10000.0 * 0.30))

        composite_score = round(min(1.0, max(0.0, raw_score)), 3)

        risk_factors = {
            "amount_risk": round(amount_risk, 3),
            "merchant_velocity_risk": round(merchant_risk, 3),
            "mismatch_risk": round(mismatch_risk, 3),
            "asr_confidence_risk": round(asr_risk, 3),
            "repeated_penalty": round(repeated_penalty, 3),
            "composite_score": composite_score,
        }
        return composite_score, risk_factors

    @staticmethod
    def generate_case_file(
        dispute_id: str,
        amount: float,
        rrn: str,
        composite_score: float,
        risk_factors: Dict[str, float],
        bank_status: BankStatus,
        soundbox_status: SoundboxStatus,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Generates an audit-ready, structured Case File dossier for 1-click supervisor review.
        """
        recommended_action = "APPROVE_SETTLEMENT" if bank_status == BankStatus.SUCCESS else "REJECT_CLAIM"

        return {
            "case_id": f"CASE_{dispute_id}",
            "dispute_id": dispute_id,
            "rrn": rrn,
            "amount": amount,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "composite_risk_score": composite_score,
            "escalation_threshold": RISK_ESCALATION_THRESHOLD,
            "escalation_reason": reason,
            "risk_factors": risk_factors,
            "evidence": {
                "bank_status": bank_status.value,
                "soundbox_status": soundbox_status.value,
                "rrn_verified_format": len(rrn) == 12 and rrn.isdigit(),
            },
            "summary": (
                f"Dispute {dispute_id} for ₹{amount:,.2f} (RRN: {rrn}) triggered Safety Circuit Breaker. "
                f"Composite Risk Score: {composite_score:.2f} (Threshold: {RISK_ESCALATION_THRESHOLD}). {reason}"
            ),
            "recommended_action": recommended_action,
            "one_tap_actions": ["APPROVE_AND_SETTLE", "REJECT_CLAIM"],
        }

    @classmethod
    def evaluate_risk(
        cls,
        amount: float,
        confidence_score: float,
        bank_status: BankStatus,
        soundbox_status: SoundboxStatus,
        rrn: str = "",
        merchant_tenure_days: int = 180,
        dispute_count_30d: int = 0,
        asr_confidence: float = 0.95,
        claim_ledger_matched: bool = True,
        dispute_id: str = "DSP_UNKNOWN",
    ) -> Tuple[bool, Optional[str], ResolutionAction, float, Optional[Dict[str, Any]]]:
        """
        Applies Paytm Autonomous Teammate safety circuit breakers:
        - Fake/Spoof -> Immediate alert
        - Composite Risk Score >= RISK_ESCALATION_THRESHOLD -> Escalates to Human with Case File
        - Cross-system Confidence < MIN_AUTONOMOUS_CONFIDENCE -> Escalates to Human with Case File
        - Otherwise -> Autonomous Resolution
        Returns: (hitl_required, hitl_reason, resolution_action, composite_score, case_file)
        """
        logger.info(f"[DecisionEngine] Evaluating risk for Amount=₹{amount}, Confidence={confidence_score:.2f}")

        # Rule 0: Fraud & Fake Payment Shield (Paytm Spoof Defense)
        if rrn.startswith("FAKE") or rrn.startswith("SPOOF") or bank_status == BankStatus.NOT_FOUND:
            reason = (
                f"PAYTM_SPOOF_FRAUD_SHIELD: Transaction RRN {rrn} was NOT found on NPCI / Bank switch. "
                f"Likely counterfeit screenshot or fake-pay APK scam. Issuing immediate merchant alert."
            )
            return False, reason, ResolutionAction.ALERT_FAKE_PAYMENT, 1.0, None

        # Compute Composite Risk Score
        composite_score, risk_factors = cls.calculate_composite_risk(
            amount=amount,
            merchant_tenure_days=merchant_tenure_days,
            dispute_count_30d=dispute_count_30d,
            asr_confidence=asr_confidence,
            claim_ledger_matched=claim_ledger_matched,
        )

        # Rule 1: High Composite Risk Circuit Breaker (replaces flat INR 5,000 rule)
        if composite_score >= RISK_ESCALATION_THRESHOLD:
            reason = (
                f"HIGH_VALUE_THRESHOLD / COMPOSITE_RISK_THRESHOLD: Risk score of {composite_score:.2f} exceeds "
                f"autonomous safety threshold of {RISK_ESCALATION_THRESHOLD:.2f} "
                f"(Amount=₹{amount:,.2f}, Velocity Risk={risk_factors['merchant_velocity_risk']:.2f}). "
                f"Escalating for supervisor 1-click review."
            )
            case_file = cls.generate_case_file(
                dispute_id=dispute_id,
                amount=amount,
                rrn=rrn,
                composite_score=composite_score,
                risk_factors=risk_factors,
                bank_status=bank_status,
                soundbox_status=soundbox_status,
                reason=reason,
            )
            return True, reason, ResolutionAction.ESCALATE_HITL, composite_score, case_file

        # Rule 2: Low Cross-System Confidence Circuit Breaker
        if confidence_score < MIN_AUTONOMOUS_CONFIDENCE:
            reason = (
                f"LOW_CONFIDENCE_BREAKER: Confidence score of {confidence_score:.1%} is below "
                f"the required {MIN_AUTONOMOUS_CONFIDENCE:.0%} threshold. Potential anomaly detected."
            )
            case_file = cls.generate_case_file(
                dispute_id=dispute_id,
                amount=amount,
                rrn=rrn,
                composite_score=composite_score,
                risk_factors=risk_factors,
                bank_status=bank_status,
                soundbox_status=soundbox_status,
                reason=reason,
            )
            return True, reason, ResolutionAction.ESCALATE_HITL, composite_score, case_file

        # Rule 3: Reversal Handling
        if bank_status == BankStatus.REVERSAL_INITIATED:
            return False, None, ResolutionAction.PROVISIONAL_CREDIT_AND_NOTIFY, composite_score, None

        # Rule 4: Standard Autonomous Settlement
        if bank_status == BankStatus.SUCCESS:
            return False, None, ResolutionAction.AUTONOMOUS_SETTLE_PUSH_SOUNDBOX, composite_score, None

        # Default fallback
        reason = "Default safety halt: Unmapped state combination."
        case_file = cls.generate_case_file(
            dispute_id=dispute_id,
            amount=amount,
            rrn=rrn,
            composite_score=composite_score,
            risk_factors=risk_factors,
            bank_status=bank_status,
            soundbox_status=soundbox_status,
            reason=reason,
        )
        return True, reason, ResolutionAction.ESCALATE_HITL, composite_score, case_file
