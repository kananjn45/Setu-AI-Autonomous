"""
SETTLE.AI - Deterministic Transaction State Resolver
Classifies transactions into strictly one of 6 canonical states:
1. CREDITED: Confirmed on ledger -> replay chime + speak last 4 digits of UTR
2. PENDING: In flight at clearing switch -> tell merchant expected resolution window
3. FAILED_REVERSAL_DUE: Failed debit -> customer auto-reverses per RBI TAT deadline (from config)
4. DEEMED_SUCCESS: Switch approved, awaiting batch ledger credit -> sync settlement + speak UTR
5. NOT_FOUND: Zero debit record -> say payment not received
6. AMBIGUOUS: Multiple matching transactions -> ask clarifying question
"""

import logging
from typing import Optional, Dict, Any, Tuple, List
from settle_ai.agent.schemas import (
    CanonicalTxState,
    BankStatus,
    LedgerStatus,
    BankSwitchResponse,
    LedgerRecord,
)
from settle_ai.agent.tools import bank_tool, ledger_tool
from settle_ai.config import (
    RBI_UPI_AUTO_REVERSAL_TAT_DAYS,
    RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR,
)

logger = logging.getLogger("settle_ai.state_resolver")


class TransactionStateResolver:
    """Deterministic state resolver implementing the 6 canonical dispute states."""

    @staticmethod
    def resolve_state(
        merchant_id: str,
        amount: float,
        rrn: Optional[str] = None,
        time_window_seconds: int = 600,
    ) -> Tuple[CanonicalTxState, Dict[str, Any]]:
        """
        Queries NPCI switch and CBS ledger to classify into strictly one canonical state.
        Returns: (CanonicalTxState, resolution_payload)
        """
        logger.info(f"[StateResolver] Resolving state: Merchant={merchant_id}, Amount=₹{amount}, RRN={rrn}")

        # 1. If explicit RRN provided
        if rrn and len(rrn.strip()) == 12 and rrn.isdigit():
            clean_rrn = rrn.strip()
            bank_resp = bank_tool.verify_transaction(rrn=clean_rrn, amount_hint=amount)
            ledger_status = ledger_tool.inspect_ledger(merchant_id=merchant_id, rrn=clean_rrn)
            return TransactionStateResolver._classify_single(
                merchant_id=merchant_id,
                amount=amount,
                rrn=clean_rrn,
                bank_resp=bank_resp,
                ledger_status=ledger_status,
            )

        # 2. If no RRN or ambiguous, search across switch for matching amounts
        matches = bank_tool.search_transactions(
            merchant_id=merchant_id,
            amount=amount,
            time_window_seconds=time_window_seconds,
        )

        # Case 6: AMBIGUOUS (Multiple matching transactions)
        if len(matches) > 1:
            clarifying_question = (
                f"Aapki dukan par pichle 10 minute mein ₹{amount:.2f} ke {len(matches)} transaction mile hain. "
                f"Kripya customer ke UTR ke aakhiri 4 ank batayein taaki sahi payment confirm ho sake."
            )
            return CanonicalTxState.AMBIGUOUS, {
                "state": CanonicalTxState.AMBIGUOUS,
                "matches_count": len(matches),
                "matched_rrns": [m.rrn for m in matches],
                "action": "PROMPT_CLARIFICATION",
                "clarifying_question": clarifying_question,
                "can_replay_chime": False,
                "response_message": clarifying_question,
            }

        # If exactly one match found by amount search
        if len(matches) == 1:
            match = matches[0]
            ledger_status = ledger_tool.inspect_ledger(merchant_id=merchant_id, rrn=match.rrn)
            return TransactionStateResolver._classify_single(
                merchant_id=merchant_id,
                amount=amount,
                rrn=match.rrn,
                bank_resp=match,
                ledger_status=ledger_status,
            )

        # Case 5: NOT_FOUND
        msg = f"Yeh bhugtan (₹{amount:.2f}) Paytm par prapt nahi hua hai. Bank switch par koi record nahi mila."
        return CanonicalTxState.NOT_FOUND, {
            "state": CanonicalTxState.NOT_FOUND,
            "rrn": rrn or "UNKNOWN",
            "amount": amount,
            "action": "INFORM_NOT_RECEIVED",
            "can_replay_chime": False,
            "response_message": msg,
        }

    @staticmethod
    def _classify_single(
        merchant_id: str,
        amount: float,
        rrn: str,
        bank_resp: BankSwitchResponse,
        ledger_status: LedgerStatus,
    ) -> Tuple[CanonicalTxState, Dict[str, Any]]:
        """Classifies a specific RRN transaction into one of the canonical states."""
        utr_last_4 = rrn[-4:]

        # Case 5: NOT_FOUND (Zero record / Fraud spoof)
        if bank_resp.status == BankStatus.NOT_FOUND:
            msg = (
                f"Bhugtan prapt nahi hua: RRN {rrn} (₹{amount:.2f}) NPCI bank switch par darj nahi hai. "
                f"Customer ke khate se koi paisa debit nahi hua. Kripya samaan na dein."
            )
            return CanonicalTxState.NOT_FOUND, {
                "state": CanonicalTxState.NOT_FOUND,
                "rrn": rrn,
                "amount": amount,
                "utr_last_4": utr_last_4,
                "action": "INFORM_NOT_RECEIVED",
                "can_replay_chime": False,
                "response_message": msg,
            }

        # Case 3: FAILED_REVERSAL_DUE (Debit failed or declined at bank)
        if bank_resp.status in (BankStatus.FAILED, BankStatus.REVERSAL_INITIATED):
            msg = (
                f"Customer ka bhugtan bank par asafal (failed) raha. "
                f"RBI TAT niyam ke tahat customer ke bank khate mein T+{RBI_UPI_AUTO_REVERSAL_TAT_DAYS} "
                f"karyadivas mein auto-reversal poora ho jayega. "
                f"(Niyamit samay se vilamb par ₹{RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR:.0f}/din ka harzana lagu hai). "
                f"Kripya customer se doosre bank se bhugtan lein."
            )
            return CanonicalTxState.FAILED_REVERSAL_DUE, {
                "state": CanonicalTxState.FAILED_REVERSAL_DUE,
                "rrn": rrn,
                "amount": amount,
                "utr_last_4": utr_last_4,
                "bank_name": bank_resp.payer_bank,
                "rbi_tat_days": RBI_UPI_AUTO_REVERSAL_TAT_DAYS,
                "compensation_per_day": RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR,
                "action": "EXPLAIN_AUTO_REVERSAL",
                "can_replay_chime": False,
                "response_message": msg,
            }

        # Case 2: PENDING (In flight at clearing house)
        if bank_resp.status == BankStatus.PENDING:
            msg = (
                f"₹{amount:.2f} ka bhugtan bank clearing switch par PENDING hai (RRN {rrn}). "
                f"Yeh aamtaur par 15 se 30 minute mein saaf ho jata hai. "
                f"Sthiti spasht hone par turant WhatsApp par soochit kar diya jayega."
            )
            return CanonicalTxState.PENDING, {
                "state": CanonicalTxState.PENDING,
                "rrn": rrn,
                "amount": amount,
                "utr_last_4": utr_last_4,
                "action": "INFORM_PENDING_WINDOW",
                "can_replay_chime": False,
                "response_message": msg,
            }

        # Case 1: CREDITED (Confirmed on ledger)
        if bank_resp.status == BankStatus.SUCCESS and ledger_status in (LedgerStatus.SETTLED, LedgerStatus.PROVISIONAL_CREDITED):
            msg = (
                f"Haan Gupta ji, {bank_resp.payer_bank} se ₹{amount:.0f} prapt hue. "
                f"UTR ke aakhiri char ank {utr_last_4} hain."
            )
            return CanonicalTxState.CREDITED, {
                "state": CanonicalTxState.CREDITED,
                "rrn": rrn,
                "amount": amount,
                "utr_last_4": utr_last_4,
                "payer_bank": bank_resp.payer_bank,
                "action": "REPLAY_CHIME_SPEAK_UTR",
                "can_replay_chime": True,
                "response_message": msg,
            }

        # Case 4: DEEMED_SUCCESS (Approved by switch, awaiting batch settlement sync)
        if bank_resp.status == BankStatus.SUCCESS and ledger_status == LedgerStatus.UNCREDITED:
            # Synchronize internal settlement ledger
            synced_rec = ledger_tool.record_settlement_sync(merchant_id=merchant_id, rrn=rrn, amount=amount)
            msg = (
                f"Bhugtan safal raha! {bank_resp.payer_bank} se ₹{amount:.0f} prapt hue. "
                f"UTR ke aakhiri char ank {utr_last_4} hain. Settlement balance mein jod diya gaya hai."
            )
            return CanonicalTxState.DEEMED_SUCCESS, {
                "state": CanonicalTxState.DEEMED_SUCCESS,
                "rrn": rrn,
                "amount": amount,
                "utr_last_4": utr_last_4,
                "payer_bank": bank_resp.payer_bank,
                "action": "SYNC_SETTLEMENT_AND_REPLAY_CHIME",
                "can_replay_chime": True,
                "ledger_record": synced_rec,
                "response_message": msg,
            }

        # Fallback default
        return CanonicalTxState.NOT_FOUND, {
            "state": CanonicalTxState.NOT_FOUND,
            "rrn": rrn,
            "amount": amount,
            "action": "INFORM_NOT_RECEIVED",
            "can_replay_chime": False,
            "response_message": f"Payment status aspasht hai. Record nahi mila.",
        }
