"""
SETTLE.AI - Cryptographic Hash-Chained Audit Logger
Implements immutable, tamper-evident SHA-256 hash chaining across all agent decisions:
- Captures: inputs, tools called, canonical state determined, action taken, reason, timestamp.
- Each entry hashes the payload concatenated with the previous block's SHA-256 hash.
- Provides cryptographic verification of compliance trail for RBI audits and internal risk reviews.
"""

import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger("settle_ai.audit_logger")

GENESIS_HASH = "0" * 64


class AuditLogEntry(BaseModel):
    entry_id: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dispute_id: str
    merchant_id: str
    inputs: Dict[str, Any]
    tools_called: List[str]
    state_determined: str
    action_taken: str
    reason: str
    prev_hash: str
    entry_hash: str


class AuditLogger:
    """Cryptographic hash-chained audit trail for autonomous decisions."""

    def __init__(self):
        self._chain: List[AuditLogEntry] = []

    @property
    def latest_hash(self) -> str:
        return self._chain[-1].entry_hash if self._chain else GENESIS_HASH

    @property
    def entries(self) -> List[AuditLogEntry]:
        return list(self._chain)

    def _compute_hash(self, entry_id: int, timestamp: str, dispute_id: str,
                      merchant_id: str, inputs: Dict[str, Any], tools_called: List[str],
                      state_determined: str, action_taken: str, reason: str,
                      prev_hash: str) -> str:
        payload = {
            "entry_id": entry_id,
            "timestamp": timestamp,
            "dispute_id": dispute_id,
            "merchant_id": merchant_id,
            "inputs": inputs,
            "tools_called": sorted(tools_called),
            "state_determined": state_determined,
            "action_taken": action_taken,
            "reason": reason,
            "prev_hash": prev_hash,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_decision(
        self,
        dispute_id: str,
        merchant_id: str,
        inputs: Dict[str, Any],
        tools_called: List[str],
        state_determined: str,
        action_taken: str,
        reason: str,
    ) -> AuditLogEntry:
        """Appends a new decision block to the cryptographically chained audit log."""
        entry_id = len(self._chain) + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        prev_hash = self.latest_hash

        entry_hash = self._compute_hash(
            entry_id=entry_id,
            timestamp=timestamp,
            dispute_id=dispute_id,
            merchant_id=merchant_id,
            inputs=inputs,
            tools_called=tools_called,
            state_determined=state_determined,
            action_taken=action_taken,
            reason=reason,
            prev_hash=prev_hash,
        )

        entry = AuditLogEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            dispute_id=dispute_id,
            merchant_id=merchant_id,
            inputs=inputs,
            tools_called=tools_called,
            state_determined=state_determined,
            action_taken=action_taken,
            reason=reason,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

        self._chain.append(entry)
        logger.info(
            f"[AuditLogger] Block #{entry_id} chained for {dispute_id}. "
            f"State={state_determined}, Hash={entry_hash[:12]}..."
        )
        return entry

    def verify_chain_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates the entire hash chain from Genesis to tip.
        Returns (is_valid, error_description).
        """
        if not self._chain:
            return True, None

        expected_prev_hash = GENESIS_HASH
        for idx, entry in enumerate(self._chain):
            if entry.prev_hash != expected_prev_hash:
                return False, f"Broken chain link at index {idx} (Block #{entry.entry_id}): expected prev_hash {expected_prev_hash}, got {entry.prev_hash}"

            recomputed_hash = self._compute_hash(
                entry_id=entry.entry_id,
                timestamp=entry.timestamp,
                dispute_id=entry.dispute_id,
                merchant_id=entry.merchant_id,
                inputs=entry.inputs,
                tools_called=entry.tools_called,
                state_determined=entry.state_determined,
                action_taken=entry.action_taken,
                reason=entry.reason,
                prev_hash=entry.prev_hash,
            )

            if entry.entry_hash != recomputed_hash:
                return False, f"Tampered block detected at index {idx} (Block #{entry.entry_id}): computed {recomputed_hash}, got {entry.entry_hash}"

            expected_prev_hash = entry.entry_hash

        return True, None

    def get_entries_for_dispute(self, dispute_id: str) -> List[AuditLogEntry]:
        """Returns all audit blocks associated with a specific dispute ID."""
        return [e for e in self._chain if e.dispute_id == dispute_id]


# Global audit logger instance
audit_logger = AuditLogger()
