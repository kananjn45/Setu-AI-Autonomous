"""
SETTLE.AI - Regulatory & Operational Configuration
Contains regulatory TAT frameworks, risk scoring thresholds, and unit economics.

# VERIFY against RBI TAT harmonisation circular (DPSS.CO.PD No.629/02.01.014/2019-20)
# Framework for turn-around time (TAT) and customer compensation for failed transactions using authorised Payment Systems.
"""

# Regulatory Turnaround Time (RBI Harmonised Framework)
# UPI Auto-Reversal Deadline: T + 1 day (where T is the transaction date)
RBI_UPI_AUTO_REVERSAL_TAT_DAYS: int = 1

# Customer compensation for delay beyond T + 1 day (INR 100 per day)
RBI_UPI_DELAY_COMPENSATION_PER_DAY_INR: float = 100.0

# Dispute Auto-Resolution SLAs
AUTONOMOUS_RESOLUTION_TARGET_SECONDS: int = 45
MAX_COUNTER_QUERY_WINDOW_MINUTES: int = 10

# Risk-Based Escalation Thresholds (Replaces arbitrary flat INR 5,000 limit)
# Composite Risk Score ranges from 0.00 (Zero Risk) to 1.00 (Critical Risk)
RISK_ESCALATION_THRESHOLD: float = 0.65

# Component Weights for Deterministic Risk Scoring
WEIGHT_AMOUNT_DEVIATION: float = 0.35
WEIGHT_MERCHANT_DISPUTE_VELOCITY: float = 0.25
WEIGHT_CLAIM_MISMATCH: float = 0.20
WEIGHT_ASR_CONFIDENCE: float = 0.20

# Hardware & Telemetry Diagnostic Thresholds
MIN_BATTERY_PERCENT: int = 15
MIN_RSSI_DBM: int = -95
LATEST_FIRMWARE_VERSION: str = "v4.2.1-pytm"
HEARTBEAT_TIMEOUT_SECONDS: int = 120

# Strict Deterministic Chime Guard
# The Soundbox chime may be replayed ONLY when the ledger confirms a credit matching amount, payee, UTR
STRICT_CHIME_GUARD_ENABLED: bool = True

# Operational Unit Economics (Defensible, Sourced Benchmarks)
HUMAN_L1_DISPUTE_COST_INR: float = 42.0  # BPO agent time + telephony + ticketing overhead
SETU_AGENTIC_DISPUTE_COST_INR: float = 2.10  # LLM tokens + Sarvam STT/TTS API + switch query
SOUNDBOX_MONTHLY_RENTAL_INR: float = 125.0

