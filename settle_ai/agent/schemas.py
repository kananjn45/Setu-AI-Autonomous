"""
SETTLE.AI - Agent Data Contracts & Pydantic Schemas
Defines interface models for Orchestrator, Bank Switch, Soundbox IoT, Ledger, and HITL Gateway.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class BankStatus(str, Enum):
    SUCCESS = "SUCCESS"  # Account debited, cleared at switch
    PENDING = "PENDING"  # In flight at clearing house
    DEBITED_NOT_CREDITED = "DEBITED_NOT_CREDITED"  # Classic sync gap
    REVERSAL_INITIATED = "REVERSAL_INITIATED"  # Auto-reversal in queue
    FAILED = "FAILED"  # Debit declined
    NOT_FOUND = "NOT_FOUND"  # Invalid RRN


class SoundboxStatus(str, Enum):
    ONLINE = "ONLINE"  # Connected and healthy
    OFFLINE = "OFFLINE"  # Network disconnected
    PACKET_DROPPED = "PACKET_DROPPED"  # Connected but missed MQTT ACK
    MUTED = "MUTED"  # Volume muted or audio hardware stall
    ACK_RECEIVED = "ACK_RECEIVED"  # Chime successfully played


class LedgerStatus(str, Enum):
    SETTLED = "SETTLED"  # Already credited to merchant balance
    UNCREDITED = "UNCREDITED"  # Missing from merchant ledger
    PROVISIONAL_CREDITED = "PROVISIONAL_CREDITED"  # Auto-provisional credit posted
    HOLD = "HOLD"  # Under dispute hold


class ResolutionAction(str, Enum):
    AUTONOMOUS_SETTLE_PUSH_SOUNDBOX = "AUTONOMOUS_SETTLE_PUSH_SOUNDBOX"
    PROVISIONAL_CREDIT_AND_NOTIFY = "PROVISIONAL_CREDIT_AND_NOTIFY"
    ESCALATE_HITL = "ESCALATE_HITL"
    REJECT_DISPUTE = "REJECT_DISPUTE"
    ALERT_FAKE_PAYMENT = "ALERT_FAKE_PAYMENT"
    TRIGGER_SALES_UPGRADE = "TRIGGER_SALES_UPGRADE"
    BROADCAST_SWITCH_ADVISORY = "BROADCAST_SWITCH_ADVISORY"


class MissionType(str, Enum):
    SERVICE_DISPUTE = "SERVICE_DISPUTE"
    FRAUD_SPOOF_DEFENSE = "FRAUD_SPOOF_DEFENSE"
    SALES_HARDWARE_UPGRADE = "SALES_HARDWARE_UPGRADE"
    SALES_WORKING_CAPITAL = "SALES_WORKING_CAPITAL"
    PROACTIVE_SWITCH_HEALTH = "PROACTIVE_SWITCH_HEALTH"


class MerchantContext(BaseModel):
    merchant_id: str = "MERCH_GUPTA_TEA"
    merchant_name: str = "Gupta Tea Stall"
    merchant_tier: str = "GOLD"  # GOLD, SILVER, PLATINUM
    monthly_gmv: float = 85000.0
    dispute_rate: float = 0.002
    device_model: str = "Soundbox 2G Classic"
    device_health_score: float = 0.45  # Low score (< 0.50) triggers proactive sales upgrade
    loan_eligible: bool = True
    loan_preapproved_limit: float = 50000.0


class DisputeChannel(str, Enum):
    INDIC_VOICE = "INDIC_VOICE"
    WHATSAPP = "WHATSAPP"
    MERCHANT_PORTAL = "MERCHANT_PORTAL"
    SOUNDBOX_KEYPRESS = "SOUNDBOX_KEYPRESS"


# --- Microservice Contract Models ---

class BankSwitchResponse(BaseModel):
    rrn: str = Field(..., description="12-digit Retrieval Reference Number")
    amount: float
    status: BankStatus
    customer_vpa: str
    payer_bank: str
    clearing_timestamp: str
    gateway_response_code: str = "00"
    raw_message: str = "Transaction completed successfully"


class SoundboxTelemetry(BaseModel):
    device_id: str
    merchant_id: str
    status: SoundboxStatus
    rssi_dbm: int = Field(default=-75, description="Cellular signal strength")
    battery_percentage: int = 85
    firmware_version: str = "v4.2.1-pytm"
    last_ping_utc: str
    pending_audio_queue: int = 0
    last_played_rrn: Optional[str] = None


class LedgerRecord(BaseModel):
    merchant_id: str
    rrn: str
    amount: float
    status: LedgerStatus
    balance_before: float
    balance_after: float
    timestamp: str
    idempotency_key: str


class DisputeGrievance(BaseModel):
    dispute_id: str
    merchant_id: str
    device_id: str
    rrn: str
    amount: float
    voice_transcript: Optional[str] = None
    channel: DisputeChannel = DisputeChannel.INDIC_VOICE
    merchant_name: str = "Merchant Partner"
    merchant_phone: str = "+919876543210"
    customer_vpa: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --- Execution Step & Audit Log ---

class StepLog(BaseModel):
    step_id: int
    node_name: str
    timestamp: str
    status: str  # STARTED, COMPLETED, HALTED, FAILED
    latency_ms: float
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


# --- LangGraph State Definition ---

class AgentState(BaseModel):
    # Dispute details
    dispute_id: str
    merchant_id: str
    device_id: str
    rrn: str
    amount: float
    voice_transcript: Optional[str] = None
    channel: DisputeChannel = DisputeChannel.INDIC_VOICE
    merchant_name: str = "Merchant Partner"
    merchant_phone: str = "+919876543210"
    customer_vpa: Optional[str] = None

    # Diagnostic sweep results
    bank_status: Optional[BankStatus] = None
    bank_details: Optional[BankSwitchResponse] = None
    soundbox_status: Optional[SoundboxStatus] = None
    soundbox_telemetry: Optional[SoundboxTelemetry] = None
    ledger_status: Optional[LedgerStatus] = None
    ledger_record: Optional[LedgerRecord] = None

    # Risk & Evaluation
    confidence_score: float = 0.0
    risk_assessment_reason: str = ""
    hitl_required: bool = False
    hitl_reason: Optional[str] = None

    # Human-in-the-loop controls
    hitl_approved: Optional[bool] = None
    hitl_supervisor_notes: Optional[str] = None
    hitl_reviewed_at: Optional[str] = None

    # Resolution
    resolution_action: Optional[ResolutionAction] = None
    soundbox_pushed: bool = False
    ledger_credited: bool = False
    notification_dispatched: bool = False
    final_resolution_message: str = ""
    is_completed: bool = False

    # Teammate Mission & Context
    mission_type: MissionType = MissionType.SERVICE_DISPUTE
    merchant_context: Optional[MerchantContext] = None
    fraud_alert_triggered: bool = False
    sales_pitch_generated: Optional[str] = None
    sales_outcome_recorded: bool = False
    proactive_advisory: Optional[str] = None
    teammate_summary: Optional[str] = None

    # Compliance & Guardrails (NeMo / RBI TAT)
    audit_hash_sha256: Optional[str] = None
    rbi_tat_compliant: bool = True

    # Execution telemetry
    execution_steps: List[StepLog] = Field(default_factory=list)
