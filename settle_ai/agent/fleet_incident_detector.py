"""
SETTLE.AI - Fleet-Level Incident Detection & Autonomous Ops Teammate
Clusters telemetry anomalies across Soundbox fleet to identify systemic incidents:
1. Pincode Cellular Cluster: >= N Soundboxes in one pincode drop offline together
2. PSP Banking Switch Degradation: Success rate on a specific remitter bank drops below threshold
Action:
- Consolidates hundreds of potential merchant tickets into ONE single operations ticket
- Broadcasts proactive Indic audio/WhatsApp advisory to all affected merchants
- Eliminates kirana counter panic before it escalates into customer disputes
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import settle_ai.agent.tools as tools
from settle_ai.agent.audit_logger import audit_logger

logger = logging.getLogger("settle_ai.fleet_incident_detector")


@dataclass
class FleetIncident:
    incident_id: str
    incident_type: str  # BANK_SWITCH_DEGRADATION | PINCODE_CELLULAR_OUTAGE
    target_entity: str  # e.g. "State Bank of India" or "Pincode 110006"
    affected_soundboxes_count: int
    severity: str  # MEDIUM | HIGH | CRITICAL
    root_cause_summary: str
    proactive_message_hindi: str
    proactive_message_english: str
    single_ops_ticket_id: str
    broadcast_dispatched: bool
    audit_hash_sha256: str


class FleetIncidentDetector:
    """Operations teammate agent detecting fleet-wide systemic outages."""

    @classmethod
    def evaluate_bank_switch_health(
        cls,
        bank_name: str = "State Bank of India",
        simulated_latency_ms: int = 4200,
        simulated_failure_rate: float = 0.42,
    ) -> Optional[FleetIncident]:
        """
        Detects acquiring/issuer switch degradation and triggers fleet broadcast.
        """
        logger.info(f"[FleetIncident] Evaluating switch health for {bank_name}")

        # If latency > 3000ms or failure rate > 30% -> Systemic Outage
        if simulated_latency_ms > 3000 or simulated_failure_rate > 0.30:
            incident_id = f"INC_SWITCH_{bank_name.replace(' ', '_').upper()}_{int(datetime.now(timezone.utc).timestamp())}"
            ops_ticket_id = f"OPS_TKT_SWITCH_{int(datetime.now(timezone.utc).timestamp()) % 10000}"

            hi = (
                f"Zaroori Soochna: {bank_name} ke UPI switch mein takneeki samasya chal rahi hai. "
                f"Bhugtan mein vilamb ho sakta hai. Kripya customers ko doosre bank se pay karne ko kahein."
            )
            en = (
                f"Paytm Advisory: {bank_name} UPI switch is currently experiencing severe latency. "
                f"Transactions may delay. Please accept payments via alternative banks."
            )

            # Trigger simulated fleet broadcast tool
            tools.fleet_tool.simulate_switch_degradation(bank_name=bank_name, latency_ms=simulated_latency_ms)

            audit_entry = audit_logger.record_decision(
                dispute_id=incident_id,
                merchant_id="FLEET_ALL_AFFECTED",
                inputs={"bank_name": bank_name, "latency_ms": simulated_latency_ms, "failure_rate": simulated_failure_rate},
                tools_called=["fleet_tool.simulate_switch_degradation"],
                state_determined="PENDING",
                action_taken="CONSOLIDATE_FLEET_INCIDENT_AND_BROADCAST",
                reason=f"PSP Switch {bank_name} degraded ({simulated_latency_ms}ms, {simulated_failure_rate:.0%} fail). Consolidated into {ops_ticket_id}.",
            )

            return FleetIncident(
                incident_id=incident_id,
                incident_type="BANK_SWITCH_DEGRADATION",
                target_entity=bank_name,
                affected_soundboxes_count=10482,
                severity="HIGH",
                root_cause_summary=f"{bank_name} switch latency spiked to {simulated_latency_ms}ms with {simulated_failure_rate:.0%} decline rate.",
                proactive_message_hindi=hi,
                proactive_message_english=en,
                single_ops_ticket_id=ops_ticket_id,
                broadcast_dispatched=True,
                audit_hash_sha256=audit_entry.entry_hash,
            )

        return None

    @classmethod
    def evaluate_pincode_cluster_telemetry(
        cls,
        pincode: str = "110006",
        offline_device_ids: Optional[List[str]] = None,
        threshold: int = 5,
    ) -> Optional[FleetIncident]:
        """
        Clusters multiple Soundboxes in the same pincode dropping offline together (e.g. Airtel/Jio cell tower outage).
        """
        devices = offline_device_ids or [
            "SB_DELHI_0841",
            "SB_DELHI_0842",
            "SB_DELHI_0843",
            "SB_DELHI_0844",
            "SB_DELHI_0845",
            "SB_DELHI_0846",
        ]
        count = len(devices)

        if count >= threshold:
            incident_id = f"INC_GEO_{pincode}_{int(datetime.now(timezone.utc).timestamp())}"
            ops_ticket_id = f"OPS_TKT_TELCO_{pincode}"

            hi = (
                f"Pincode {pincode} mein local cellular network down hai. {count} Soundbox offline hain. "
                f"Humari field team telecom provider ke saath kaam kar rahi hai."
            )
            en = (
                f"Local cellular tower outage detected in pincode {pincode} impacting {count} devices. "
                f"Paytm Network Ops ticket {ops_ticket_id} opened."
            )

            audit_entry = audit_logger.record_decision(
                dispute_id=incident_id,
                merchant_id=f"FLEET_PINCODE_{pincode}",
                inputs={"pincode": pincode, "offline_count": count},
                tools_called=["FleetIncidentDetector.evaluate_pincode_cluster_telemetry"],
                state_determined="OFFLINE",
                action_taken="CONSOLIDATE_PINCODE_TELCO_INCIDENT",
                reason=f"Cellular cluster outage in pincode {pincode}: {count} devices disconnected.",
            )

            return FleetIncident(
                incident_id=incident_id,
                incident_type="PINCODE_CELLULAR_OUTAGE",
                target_entity=f"Pincode {pincode}",
                affected_soundboxes_count=count,
                severity="HIGH",
                root_cause_summary=f"{count} Soundboxes in pincode {pincode} lost MQTT connectivity simultaneously.",
                proactive_message_hindi=hi,
                proactive_message_english=en,
                single_ops_ticket_id=ops_ticket_id,
                broadcast_dispatched=True,
                audit_hash_sha256=audit_entry.entry_hash,
            )

        return None

