"""
SETTLE.AI - Counter-Side Rapid Payment Adjudicator
Resolves counter-side shopkeeper/customer disputes in real-time ("Setu, 500 aaya kya?"):
- Matches transactions within the last N minutes (configurable, default 10)
- Speaks verified status + last 4 digits of UTR in merchant's Indic language in <3s
- Handles single match, multiple matches (clarification), and not found
- Strictly enforces SoundboxChimeGuard (zero false chimes)
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from settle_ai.config import MAX_COUNTER_QUERY_WINDOW_MINUTES
from settle_ai.agent.schemas import CanonicalTxState, BankStatus, LedgerStatus
import settle_ai.agent.tools as tools
from settle_ai.agent.state_resolver import TransactionStateResolver
from settle_ai.agent.chime_guard import SoundboxChimeGuard
from settle_ai.agent.audit_logger import audit_logger

logger = logging.getLogger("settle_ai.counter_adjudicator")


@dataclass
class CounterAdjudicationResult:
    verdict: str  # CONFIRMED_CREDITED | MULTIPLE_MATCHES | NOT_RECEIVED | PENDING | FAILED
    amount: float
    canonical_state: CanonicalTxState
    can_replay_chime: bool
    chime_played: bool
    rrn: Optional[str]
    utr_last_4: Optional[str]
    spoken_response_hindi: str
    spoken_response_english: str
    matching_transactions_count: int
    matched_rrns: List[str]
    audit_hash_sha256: str


class CounterAdjudicator:
    """Instant counter-side verification for kirana disputes."""

    @classmethod
    def adjudicate_counter_query(
        cls,
        merchant_id: str,
        amount: float,
        device_id: str = "SB_DELHI_0841",
        window_minutes: int = MAX_COUNTER_QUERY_WINDOW_MINUTES,
        utr_hint: Optional[str] = None,
        merchant_name: str = "Gupta ji",
    ) -> CounterAdjudicationResult:
        """
        Adjudicates a spoken grievance at the billing counter.
        Example: "Setu, 500 aaya kya?"
        """
        logger.info(
            f"[CounterAdjudicator] Evaluating counter query: Merchant={merchant_id}, "
            f"Amount=₹{amount}, Window={window_minutes}m, UTR Hint={utr_hint}"
        )

        # 1. If explicit UTR hint (or last 4 digits) provided, look up directly
        if utr_hint and len(utr_hint.strip()) >= 4:
            clean_hint = utr_hint.strip()
            # If 12 digits, resolve state directly
            if len(clean_hint) == 12 and clean_hint.isdigit():
                canonical_state, res_payload = TransactionStateResolver.resolve_state(
                    merchant_id=merchant_id,
                    amount=amount,
                    rrn=clean_hint,
                    time_window_seconds=window_minutes * 60,
                )
                return cls._build_result_from_single(
                    merchant_id=merchant_id,
                    device_id=device_id,
                    amount=amount,
                    rrn=clean_hint,
                    canonical_state=canonical_state,
                    res_payload=res_payload,
                    merchant_name=merchant_name,
                )

        # 2. Search for transactions in the time window matching the exact amount
        matches = tools.bank_tool.search_transactions(
            merchant_id=merchant_id,
            amount=amount,
            time_window_seconds=window_minutes * 60,
        )

        # Filter by UTR hint (last 4 digits) if provided
        if utr_hint and len(utr_hint.strip()) >= 4:
            hint_suffix = utr_hint.strip()[-4:]
            matches = [m for m in matches if m.rrn.endswith(hint_suffix)]

        matched_rrns = [m.rrn for m in matches]

        # Case A: Multiple matching transactions (Ambiguous)
        if len(matches) > 1:
            clarify_hi = (
                f"Aapki dukan par pichle {window_minutes} minute mein ₹{amount:.0f} ke {len(matches)} payment mile hain. "
                f"Kripya customer ke UTR ke aakhiri char ank batayein taaki confirm kar sakein."
            )
            clarify_en = (
                f"Found {len(matches)} payments of ₹{amount:.0f} in the last {window_minutes} minutes. "
                f"Please tell the last 4 digits of the customer's UTR."
            )

            audit_entry = audit_logger.record_decision(
                dispute_id=f"COUNTER_{int(datetime.now(timezone.utc).timestamp())}",
                merchant_id=merchant_id,
                inputs={"amount": amount, "window_minutes": window_minutes, "utr_hint": utr_hint},
                tools_called=["bank_tool.search_transactions"],
                state_determined=CanonicalTxState.AMBIGUOUS.value,
                action_taken="PROMPT_CLARIFICATION",
                reason=f"Found {len(matches)} matching payments without differentiating UTR.",
            )

            return CounterAdjudicationResult(
                verdict="MULTIPLE_MATCHES",
                amount=amount,
                canonical_state=CanonicalTxState.AMBIGUOUS,
                can_replay_chime=False,
                chime_played=False,
                rrn=None,
                utr_last_4=None,
                spoken_response_hindi=clarify_hi,
                spoken_response_english=clarify_en,
                matching_transactions_count=len(matches),
                matched_rrns=matched_rrns,
                audit_hash_sha256=audit_entry.entry_hash,
            )

        # Case B: Exactly one matching transaction found
        if len(matches) == 1:
            match = matches[0]
            canonical_state, res_payload = TransactionStateResolver.resolve_state(
                merchant_id=merchant_id,
                amount=amount,
                rrn=match.rrn,
                time_window_seconds=window_minutes * 60,
            )
            return cls._build_result_from_single(
                merchant_id=merchant_id,
                device_id=device_id,
                amount=amount,
                rrn=match.rrn,
                canonical_state=canonical_state,
                res_payload=res_payload,
                merchant_name=merchant_name,
            )

        # Case C: Zero matching transactions found in window
        not_found_hi = (
            f"Kripya dhyan dein, pichle {window_minutes} minute mein ₹{amount:.0f} ka koi payment prapt nahi hua hai. "
            f"Customer se kahein ki UPI app par transaction status dobara check karein."
        )
        not_found_en = (
            f"No payment of ₹{amount:.0f} received in the last {window_minutes} minutes. "
            f"Please ask customer to verify in their UPI app."
        )

        audit_entry = audit_logger.record_decision(
            dispute_id=f"COUNTER_{int(datetime.now(timezone.utc).timestamp())}",
            merchant_id=merchant_id,
            inputs={"amount": amount, "window_minutes": window_minutes, "utr_hint": utr_hint},
            tools_called=["bank_tool.search_transactions"],
            state_determined=CanonicalTxState.NOT_FOUND.value,
            action_taken="INFORM_NOT_RECEIVED",
            reason=f"Zero matching payments of ₹{amount:.2f} in last {window_minutes}m.",
        )

        return CounterAdjudicationResult(
            verdict="NOT_RECEIVED",
            amount=amount,
            canonical_state=CanonicalTxState.NOT_FOUND,
            can_replay_chime=False,
            chime_played=False,
            rrn=None,
            utr_last_4=None,
            spoken_response_hindi=not_found_hi,
            spoken_response_english=not_found_en,
            matching_transactions_count=0,
            matched_rrns=[],
            audit_hash_sha256=audit_entry.entry_hash,
        )

    @classmethod
    def _build_result_from_single(
        cls,
        merchant_id: str,
        device_id: str,
        amount: float,
        rrn: str,
        canonical_state: CanonicalTxState,
        res_payload: Dict[str, Any],
        merchant_name: str,
    ) -> CounterAdjudicationResult:
        utr_last_4 = rrn[-4:]
        payer_bank = res_payload.get("payer_bank", "Bank")

        # Check Chime Guard
        can_replay = res_payload.get("can_replay_chime", False)
        chime_played = False
        if can_replay and canonical_state in (CanonicalTxState.CREDITED, CanonicalTxState.DEEMED_SUCCESS):
            chime_ok, _ = SoundboxChimeGuard.verify_chime_authorization(
                merchant_id=merchant_id,
                claimed_amount=amount,
                rrn=rrn,
            )
            if chime_ok:
                tools.soundbox_tool.push_audio_chirp(device_id=device_id, rrn=rrn, amount=amount)
                chime_played = True

        if canonical_state in (CanonicalTxState.CREDITED, CanonicalTxState.DEEMED_SUCCESS):
            verdict = "CONFIRMED_CREDITED"
            spoken_hi = (
                f"Haan {merchant_name}, {payer_bank} se ₹{amount:.0f} prapt hue. "
                f"UTR ke aakhiri char ank {utr_last_4} hain."
            )
            spoken_en = (
                f"Yes {merchant_name}, received ₹{amount:.0f} via {payer_bank}. "
                f"Last 4 digits of UTR are {utr_last_4}."
            )
        elif canonical_state == CanonicalTxState.PENDING:
            verdict = "PENDING"
            spoken_hi = (
                f"₹{amount:.0f} ka payment bank clearing switch par PENDING hai (UTR {utr_last_4}). "
                f"Kripya 15-30 minute pratiksha karein."
            )
            spoken_en = f"Payment of ₹{amount:.0f} is pending clearing at {payer_bank}. Expected window 15-30 mins."
        elif canonical_state == CanonicalTxState.FAILED_REVERSAL_DUE:
            verdict = "FAILED"
            spoken_hi = (
                f"Customer ka bhugtan asafal (failed) raha. Paisa customer ke khate mein "
                f"auto-reverse ho jayega. Kripya samaan na dein ya doosre madhyam se bhugtan lein."
            )
            spoken_en = f"Payment failed at customer's bank. Amount will auto-reverse to customer account."
        else:
            verdict = "NOT_RECEIVED"
            spoken_hi = f"₹{amount:.0f} ka bhugtan prapt nahi hua hai."
            spoken_en = f"Payment of ₹{amount:.0f} was not received."

        audit_entry = audit_logger.record_decision(
            dispute_id=f"COUNTER_{int(datetime.now(timezone.utc).timestamp())}",
            merchant_id=merchant_id,
            inputs={"amount": amount, "rrn": rrn},
            tools_called=["TransactionStateResolver.resolve_state"],
            state_determined=canonical_state.value,
            action_taken=f"COUNTER_ADJUDICATE_{verdict}",
            reason=f"Counter resolution for ₹{amount:.2f} (UTR {utr_last_4}): {verdict}",
        )

        return CounterAdjudicationResult(
            verdict=verdict,
            amount=amount,
            canonical_state=canonical_state,
            can_replay_chime=can_replay,
            chime_played=chime_played,
            rrn=rrn,
            utr_last_4=utr_last_4,
            spoken_response_hindi=spoken_hi,
            spoken_response_english=spoken_en,
            matching_transactions_count=1,
            matched_rrns=[rrn],
            audit_hash_sha256=audit_entry.entry_hash,
        )

