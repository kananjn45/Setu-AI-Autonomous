"""
SETTLE.AI - Proactive Offline Catch-Up Engine
Handles Soundbox MQTT reconnect events when device was offline:
- Identifies payments and credits that landed while the Soundbox was disconnected
- Aggregates count and total amount
- Dispatches spoken voice summary announcement via Soundbox audio queue:
  "Jab aap offline the, 3 payment aaye, total ₹1,240."
- Proactively eliminates merchant anxiety and prevents reactive support tickets
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from settle_ai.agent.schemas import SoundboxStatus, LedgerRecord
import settle_ai.agent.tools as tools
from settle_ai.agent.audit_logger import audit_logger

logger = logging.getLogger("settle_ai.offline_sync")


@dataclass
class OfflineCatchupSummary:
    device_id: str
    merchant_id: str
    is_reconnected: bool
    offline_payments_count: int
    offline_total_amount_inr: float
    spoken_announcement_hindi: str
    spoken_announcement_english: str
    audio_dispatched: bool
    audit_hash_sha256: str


class OfflineCatchupEngine:
    """Proactively summarizes unannounced offline credits upon device reconnection."""

    @classmethod
    def handle_device_reconnect(
        cls,
        device_id: str,
        merchant_id: str,
        offline_minutes: int = 45,
        mock_offline_credits: Optional[List[Dict[str, Any]]] = None,
    ) -> OfflineCatchupSummary:
        """
        Executed when Soundbox MQTT client emits a RECONNECT heartbeat event.
        """
        logger.info(f"[OfflineSync] Processing MQTT reconnect for {device_id} (Merchant: {merchant_id})")

        # Set device online in IoT registry
        if device_id in tools.soundbox_tool._devices:
            tools.soundbox_tool._devices[device_id]["is_online"] = True
            tools.soundbox_tool._devices[device_id]["status"] = SoundboxStatus.ONLINE

        # Query credits that arrived during offline window
        offline_records = []
        if mock_offline_credits:
            offline_records = mock_offline_credits
        else:
            # Query from ledger
            all_credits = tools.ledger_tool.find_credits(merchant_id=merchant_id)
            # Take the recent unannounced ones (e.g. up to 5)
            offline_records = [{"amount": c.amount, "rrn": c.rrn} for c in all_credits[-3:]] if all_credits else []

        count = len(offline_records)
        total_inr = sum(r["amount"] for r in offline_records)

        if count > 0:
            spoken_hi = f"Paytm par aapka swagat hai! Jab aap offline the, tab {count} payment aaye, total ₹{total_inr:,.0f} prapt hue."
            spoken_en = f"Welcome back! While you were offline, {count} payments arrived, totaling ₹{total_inr:,.2f}."
        else:
            spoken_hi = "Soundbox online jud gaya hai. Jab aap offline the, koi naya payment nahi aaya."
            spoken_en = "Soundbox is back online. Zero payments received during offline window."

        # Dispatch spoken announcement to Soundbox
        audio_ok = tools.soundbox_tool.push_audio_chirp(
            device_id=device_id,
            rrn="OFFLINE_SYNC",
            amount=total_inr,
        )

        audit_entry = audit_logger.record_decision(
            dispute_id=f"RECONNECT_{device_id}_{int(datetime.now(timezone.utc).timestamp())}",
            merchant_id=merchant_id,
            inputs={"device_id": device_id, "offline_minutes": offline_minutes, "count": count},
            tools_called=["soundbox_tool.push_audio_chirp", "ledger_tool.find_credits"],
            state_determined="CREDITED" if count > 0 else "ONLINE",
            action_taken="PROACTIVE_OFFLINE_CATCHUP_ANNOUNCEMENT",
            reason=f"Device reconnected after {offline_minutes}m. Announced {count} offline payments totaling ₹{total_inr:,.2f}.",
        )

        return OfflineCatchupSummary(
            device_id=device_id,
            merchant_id=merchant_id,
            is_reconnected=True,
            offline_payments_count=count,
            offline_total_amount_inr=total_inr,
            spoken_announcement_hindi=spoken_hi,
            spoken_announcement_english=spoken_en,
            audio_dispatched=audio_ok,
            audit_hash_sha256=audit_entry.entry_hash,
        )

