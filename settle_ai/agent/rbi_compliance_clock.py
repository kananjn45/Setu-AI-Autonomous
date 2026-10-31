"""
SETTLE.AI - RBI Turnaround-Time (TAT) Harmonisation Compliance Clock
Tracks regulatory auto-reversal clocks for failed UPI transactions:
- Cites RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20
  ("Harmonisation of Turn Around Time (TAT) and customer compensation for failed transactions")
- Auto-Reversal Deadline: T + 1 day
- Fixed Customer Compensation: ₹100 per day of delay beyond T + 1
States:
- WITHIN_TAT: Reversal window is fully compliant (< 20 hours)
- APPROACHING_DEADLINE: Within 4 hours of T+1 regulatory breach
- BREACHED: T+1 deadline exceeded; computes accrued statutory liability in INR
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from settle_ai.config import (
    RBI_UPI_AUTO_REVERSAL_TAT_DAYS,
    RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR,
)
from settle_ai.agent.audit_logger import audit_logger

logger = logging.getLogger("settle_ai.rbi_compliance_clock")


@dataclass
class RBIComplianceStatus:
    rrn: str
    amount: float
    transaction_time_utc: str
    tat_deadline_utc: str
    elapsed_hours: float
    remaining_hours: float
    clock_state: str  # WITHIN_TAT | APPROACHING_DEADLINE | BREACHED
    days_overdue: int
    accrued_compensation_inr: float
    circular_citation: str
    advisory_summary: str
    audit_hash_sha256: str


class RBIComplianceClock:
    """Evaluates transactions against the RBI Harmonised Turn Around Time framework."""

    CIRCULAR_ID = "RBI/2019-20/67 (DPSS.CO.PD No.629/02.01.014/2019-20)"

    @classmethod
    def evaluate_compliance(
        cls,
        rrn: str,
        amount: float,
        transaction_time_iso: str,
        current_time_iso: Optional[str] = None,
    ) -> RBIComplianceStatus:
        """
        Computes elapsed regulatory time, auto-reversal deadline, and statutory compensation.
        """
        try:
            tx_dt = datetime.fromisoformat(transaction_time_iso.replace("Z", "+00:00"))
        except Exception:
            tx_dt = datetime.now(timezone.utc) - timedelta(hours=2)

        now_dt = (
            datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            if current_time_iso
            else datetime.now(timezone.utc)
        )

        tat_deadline_dt = tx_dt + timedelta(days=RBI_UPI_AUTO_REVERSAL_TAT_DAYS)
        elapsed_seconds = max(0.0, (now_dt - tx_dt).total_seconds())
        elapsed_hours = round(elapsed_seconds / 3600.0, 1)

        deadline_seconds = RBI_UPI_AUTO_REVERSAL_TAT_DAYS * 24 * 3600
        remaining_seconds = (tat_deadline_dt - now_dt).total_seconds()
        remaining_hours = round(max(0.0, remaining_seconds / 3600.0), 1)

        # Classify state
        if remaining_seconds <= 0:
            clock_state = "BREACHED"
            seconds_overdue = abs(remaining_seconds)
            days_overdue = math.ceil(seconds_overdue / 86400.0)
            accrued_comp = days_overdue * RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR
            advisory = (
                f"RBI TAT BREACHED by {round(seconds_overdue / 3600.0, 1)} hours ({days_overdue} day(s)). "
                f"Statutory compensation liability accrued: ₹{accrued_comp:.0f} "
                f"(₹{RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR:.0f}/day per {cls.CIRCULAR_ID})."
            )
        elif remaining_seconds <= 4 * 3600:
            clock_state = "APPROACHING_DEADLINE"
            days_overdue = 0
            accrued_comp = 0.0
            advisory = (
                f"URGENT: Transaction is within {remaining_hours}h of T+{RBI_UPI_AUTO_REVERSAL_TAT_DAYS} "
                f"RBI auto-reversal deadline. Priority clearing requested to avoid ₹{RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR:.0f}/day penalty."
            )
        else:
            clock_state = "WITHIN_TAT"
            days_overdue = 0
            accrued_comp = 0.0
            advisory = (
                f"Within regulatory T+{RBI_UPI_AUTO_REVERSAL_TAT_DAYS} window ({remaining_hours}h remaining). "
                f"Auto-reversal compliant with {cls.CIRCULAR_ID}."
            )

        audit_entry = audit_logger.record_decision(
            dispute_id=f"RBI_CLOCK_{rrn}",
            merchant_id="NPCI_REMITTER_BANK",
            inputs={"rrn": rrn, "amount": amount, "elapsed_hours": elapsed_hours},
            tools_called=["RBIComplianceClock.evaluate_compliance"],
            state_determined=clock_state,
            action_taken="CALCULATE_TAT_COMPENSATION",
            reason=advisory,
        )

        return RBIComplianceStatus(
            rrn=rrn,
            amount=amount,
            transaction_time_utc=tx_dt.isoformat(),
            tat_deadline_utc=tat_deadline_dt.isoformat(),
            elapsed_hours=elapsed_hours,
            remaining_hours=remaining_hours,
            clock_state=clock_state,
            days_overdue=days_overdue,
            accrued_compensation_inr=accrued_comp,
            circular_citation=cls.CIRCULAR_ID,
            advisory_summary=advisory,
            audit_hash_sha256=audit_entry.entry_hash,
        )

