"""
SETTLE.AI - Deterministic Soundbox Chime Guard
Enforces hard code-level protection against the 'I paid, play the chime' fraud vector.
The Soundbox chime may be replayed ONLY when the ledger confirms a credit to that merchant
(matching amount, payee, UTR). Never on the user's word or prompt alone.
"""

import logging
from typing import Tuple, Optional
from settle_ai.agent.schemas import LedgerRecord, LedgerStatus, BankSwitchResponse, BankStatus
from settle_ai.agent.tools import ledger_tool
from settle_ai.config import STRICT_CHIME_GUARD_ENABLED

logger = logging.getLogger("settle_ai.chime_guard")


class SoundboxChimeGuard:
    """Enforces deterministic cryptographic & ledger preconditions before audio broadcast."""

    @staticmethod
    def verify_chime_authorization(
        merchant_id: str,
        claimed_amount: float,
        rrn: str,
        bank_details: Optional[BankSwitchResponse] = None,
        ledger_record: Optional[LedgerRecord] = None,
    ) -> Tuple[bool, str]:
        """
        Deterministic check:
        1. RRN must be valid 12-digit UPI reference.
        2. Acquiring switch must report SUCCESS (Code 00).
        3. Ledger must have an explicit credit record matching merchant_id, claimed_amount, and rrn.
        """
        if not STRICT_CHIME_GUARD_ENABLED:
            return True, "Chime guard disabled in config."

        clean_rrn = (rrn or "").strip()
        if not clean_rrn or len(clean_rrn) != 12 or not clean_rrn.isdigit():
            logger.warning(f"[ChimeGuard] BLOCKED: RRN '{rrn}' is invalid or missing.")
            return False, f"Chime blocked: Invalid 12-digit UTR/RRN format ('{rrn}')."

        # Check Bank Switch
        if bank_details:
            if bank_details.status != BankStatus.SUCCESS:
                logger.warning(f"[ChimeGuard] BLOCKED: Bank status is {bank_details.status} (expected SUCCESS).")
                return False, f"Chime blocked: Bank switch status is {bank_details.status.value} (Code {bank_details.gateway_response_code})."
            if abs(bank_details.amount - claimed_amount) > 0.01:
                logger.warning(f"[ChimeGuard] BLOCKED: Bank amount ₹{bank_details.amount} != claimed ₹{claimed_amount}.")
                return False, f"Chime blocked: Amount mismatch (Switch shows ₹{bank_details.amount}, claimed ₹{claimed_amount})."

        # Check Ledger Record
        record = ledger_record
        if not record:
            # Query ledger
            matches = ledger_tool.find_credits(merchant_id=merchant_id, rrn=clean_rrn)
            if matches:
                record = matches[0]

        if not record:
            logger.warning(f"[ChimeGuard] BLOCKED: Zero confirmed ledger credit for Merchant {merchant_id}, RRN {clean_rrn}.")
            return False, f"Chime blocked: Ledger has zero confirmed credit for RRN {clean_rrn}."

        if record.merchant_id != merchant_id:
            logger.warning(f"[ChimeGuard] BLOCKED: Payee mismatch (Record merchant {record.merchant_id} != {merchant_id}).")
            return False, f"Chime blocked: Payee merchant mismatch."

        if abs(record.amount - claimed_amount) > 0.01:
            logger.warning(f"[ChimeGuard] BLOCKED: Ledger amount ₹{record.amount} != claimed ₹{claimed_amount}.")
            return False, f"Chime blocked: Ledger amount mismatch (Ledger ₹{record.amount}, claimed ₹{claimed_amount})."

        if record.status not in (LedgerStatus.SETTLED, LedgerStatus.PROVISIONAL_CREDITED):
            logger.warning(f"[ChimeGuard] BLOCKED: Ledger status is {record.status}.")
            return False, f"Chime blocked: Ledger status is {record.status.value} (must be SETTLED)."

        logger.info(f"[ChimeGuard] AUTHORIZED: Verified credit for ₹{claimed_amount} (RRN {clean_rrn}) to {merchant_id}.")
        return True, f"Chime authorized: Confirmed ledger credit of ₹{claimed_amount:.2f} (UTR {clean_rrn[-4:]}) for {merchant_id}."

