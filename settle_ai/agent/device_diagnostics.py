"""
SETTLE.AI - Soundbox Hardware Telemetry & Device Diagnostics Engine
Inspects IoT telemetry before assuming payment failure:
- Volume level (volume == 0 -> remote unmute)
- Low battery (< 15% -> recharge prompt)
- Weak signal (RSSI < -95 dBm -> repositioning prompt)
- Outdated firmware -> mock OTA push
- Offline status -> flagged for proactive catch-up
Assigns deterministic root-cause labels for operations intelligence.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from settle_ai.config import (
    MIN_BATTERY_PERCENT,
    MIN_RSSI_DBM,
    LATEST_FIRMWARE_VERSION,
)
from settle_ai.agent.schemas import (
    SoundboxTelemetry,
    SoundboxStatus,
    BankStatus,
    LedgerStatus,
    RootCauseLabel,
    CanonicalTxState,
)
import settle_ai.agent.tools as tools

logger = logging.getLogger("settle_ai.device_diagnostics")


@dataclass
class DeviceDiagnosticResult:
    has_device_issue: bool
    root_cause: Optional[RootCauseLabel]
    remediation_applied: Optional[str]
    advisory_message_hindi: Optional[str]
    advisory_message_english: Optional[str]
    telemetry_snapshot: Dict[str, Any]


class DeviceDiagnosticsEngine:
    """Deterministic diagnostics for physical Soundbox hardware issues."""

    @classmethod
    def diagnose_device(
        cls,
        telemetry: Optional[SoundboxTelemetry],
        device_tool: Optional[tools.SoundboxIoTTool] = None,
    ) -> DeviceDiagnosticResult:
        """
        Diagnoses physical hardware health of the merchant Soundbox.
        Applies automated remote remediations (volume adjustment, OTA update) where feasible.
        """
        if not telemetry:
            return DeviceDiagnosticResult(
                has_device_issue=False,
                root_cause=None,
                remediation_applied=None,
                advisory_message_hindi=None,
                advisory_message_english=None,
                telemetry_snapshot={},
            )

        device_tool = device_tool or tools.soundbox_tool
        remediation: Optional[str] = None
        advisory_hi: Optional[str] = None
        advisory_en: Optional[str] = None
        root_cause: Optional[RootCauseLabel] = None
        has_issue = False

        snapshot = {
            "device_id": telemetry.device_id,
            "status": telemetry.status.value,
            "volume_level": telemetry.volume_level,
            "battery_percentage": telemetry.battery_percentage,
            "rssi_dbm": telemetry.rssi_dbm,
            "firmware_version": telemetry.firmware_version,
            "is_online": telemetry.is_online,
        }

        # 1. Check Volume / Mute
        if telemetry.volume_level == 0 or telemetry.status == SoundboxStatus.MUTED:
            has_issue = True
            root_cause = RootCauseLabel.DEVICE_MUTED
            # Remotely set volume back to optimal 80%
            success = device_tool.set_volume_remote(telemetry.device_id, 80)
            if success:
                remediation = f"Remotely restored Soundbox volume from {telemetry.volume_level}% to 80%."
                advisory_hi = "Aapke Soundbox ka volume band (mute) tha. Humne use remote se 80% par theek kar diya hai."
                advisory_en = "Your Soundbox volume was muted. We remotely restored it to 80%."
            else:
                advisory_hi = "Aapke Soundbox ka volume band hai. Kripya device ke volume button se aawaz badhayein."
                advisory_en = "Your Soundbox is muted. Please increase the volume using device buttons."

        # 2. Check Device Offline
        elif not telemetry.is_online or telemetry.status == SoundboxStatus.OFFLINE:
            has_issue = True
            root_cause = RootCauseLabel.CREDITED_DEVICE_OFFLINE
            advisory_hi = "Aapka Soundbox filhaal offline hai. Kripya SIM signal ya charging check karein."
            advisory_en = "Your Soundbox is currently offline. Please check SIM connectivity and power."

        # 3. Check Battery Status (< 15%)
        elif telemetry.battery_percentage < MIN_BATTERY_PERCENT:
            has_issue = True
            root_cause = RootCauseLabel.DEVICE_LOW_POWER
            advisory_hi = f"Soundbox ki battery bohot kam hai ({telemetry.battery_percentage}%). Kripya turant charger lagayein taaki chime miss na ho."
            advisory_en = f"Soundbox battery is critically low ({telemetry.battery_percentage}%). Please plug into charger to avoid missed chimes."

        # 4. Check Cellular Signal Strength (RSSI < -95 dBm)
        elif telemetry.rssi_dbm < MIN_RSSI_DBM:
            has_issue = True
            root_cause = RootCauseLabel.WEAK_SIGNAL
            advisory_hi = f"Soundbox ka 4G signal kamzor hai ({telemetry.rssi_dbm} dBm). Kripya device ko dukan ke counter ke paas reposition karein."
            advisory_en = f"Soundbox cellular signal is weak ({telemetry.rssi_dbm} dBm). Please reposition the device closer to the shop entrance."

        # 5. Check Firmware Version
        if telemetry.firmware_version != LATEST_FIRMWARE_VERSION:
            ota_success = device_tool.push_firmware_ota(telemetry.device_id, LATEST_FIRMWARE_VERSION)
            if ota_success:
                ota_rem = f"Pushed OTA firmware upgrade from {telemetry.firmware_version} to {LATEST_FIRMWARE_VERSION}."
                remediation = f"{remediation} | {ota_rem}" if remediation else ota_rem

        return DeviceDiagnosticResult(
            has_device_issue=has_issue,
            root_cause=root_cause,
            remediation_applied=remediation,
            advisory_message_hindi=advisory_hi,
            advisory_message_english=advisory_en,
            telemetry_snapshot=snapshot,
        )

    @classmethod
    def determine_overall_root_cause(
        cls,
        canonical_state: Optional[CanonicalTxState],
        device_diag: Optional[DeviceDiagnosticResult],
        bank_status: Optional[BankStatus],
        rrn: str = "",
    ) -> RootCauseLabel:
        """
        Determines the single definitive root-cause label for the dispute ticket.
        Labels: PAYER_BANK_DECLINE | NPCI_TIMEOUT | CREDITED_DEVICE_OFFLINE |
                DEVICE_MUTED | DEVICE_LOW_POWER | WEAK_SIGNAL | FALSE_CLAIM | OTHER
        """
        # Fraud / False claim check
        if rrn.startswith("FAKE") or rrn.startswith("SPOOF") or canonical_state == CanonicalTxState.NOT_FOUND:
            return RootCauseLabel.FALSE_CLAIM

        # 1. Payment failures at bank/switch
        if canonical_state == CanonicalTxState.FAILED_REVERSAL_DUE or bank_status in (
            BankStatus.FAILED,
            BankStatus.REVERSAL_INITIATED,
        ):
            return RootCauseLabel.PAYER_BANK_DECLINE

        if bank_status == BankStatus.PENDING:
            return RootCauseLabel.NPCI_TIMEOUT

        # 2. Hardware / Telemetry issues (applicable when payment was cleared / credited)
        if device_diag and device_diag.root_cause in (
            RootCauseLabel.DEVICE_MUTED,
            RootCauseLabel.DEVICE_LOW_POWER,
            RootCauseLabel.WEAK_SIGNAL,
            RootCauseLabel.CREDITED_DEVICE_OFFLINE,
        ):
            return device_diag.root_cause

        if device_diag and device_diag.telemetry_snapshot.get("status") == SoundboxStatus.PACKET_DROPPED.value:
            return RootCauseLabel.CREDITED_DEVICE_OFFLINE

        return RootCauseLabel.OTHER
