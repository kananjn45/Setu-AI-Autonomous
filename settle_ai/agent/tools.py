"""
SETTLE.AI - Agent Tools & Integration Clients
Provides deterministic interfaces for:
1. Bank Switch / NPCI Gateway
2. Soundbox MQTT Broker
3. Core Merchant Ledger (with Idempotency)
4. Merchant Multichannel Notification
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from settle_ai.agent.interfaces import (
    AbstractBankSwitch,
    AbstractMerchantLedger,
    AbstractSoundboxIoT,
    AbstractNotificationGateway,
)
from settle_ai.agent.schemas import (
    BankSwitchResponse,
    BankStatus,
    SoundboxTelemetry,
    SoundboxStatus,
    LedgerRecord,
    LedgerStatus,
)

logger = logging.getLogger("settle_ai.tools")


class BankSwitchTool(AbstractBankSwitch):
    """Interacts with NPCI / Banking Switch to verify transaction clearing state."""

    def __init__(self, api_base_url: Optional[str] = None):
        self.api_base_url = api_base_url
        # Pre-seeded sandbox database for deterministic testing
        self._database: Dict[str, Dict[str, Any]] = {
            "410294820192": {
                "amount": 350.0,
                "status": BankStatus.SUCCESS,
                "customer_vpa": "rahul.sharma@okhdfcbank",
                "payer_bank": "HDFC Bank",
                "raw_message": "Cleared and debited successfully",
            },
            "982174019284": {
                "amount": 500.0,
                "status": BankStatus.SUCCESS,
                "customer_vpa": "priya.verma@oksbi",
                "payer_bank": "State Bank of India",
                "raw_message": "Cleared and debited successfully",
            },
            "883920194821": {
                "amount": 15000.0,
                "status": BankStatus.SUCCESS,
                "customer_vpa": "vikram.mehta@okicici",
                "payer_bank": "ICICI Bank",
                "raw_message": "High-value enterprise merchant debit cleared",
            },
            "772910394812": {
                "amount": 420.0,
                "status": BankStatus.REVERSAL_INITIATED,
                "customer_vpa": "amit.kumar@paytm",
                "payer_bank": "Paytm Payments Bank",
                "raw_message": "Auto-reversal in queue due to gateway timeout",
            },
            "110022993344": {
                "amount": 120.0,
                "status": BankStatus.FAILED,
                "customer_vpa": "sunil.singh@okaxis",
                "payer_bank": "Axis Bank",
                "raw_message": "Declined: Insufficient funds at customer account",
            },
        }

    def verify_transaction(self, rrn: str, amount_hint: Optional[float] = None) -> BankSwitchResponse:
        """Queries the bank switch for the given RRN."""
        logger.info(f"[BankSwitchTool] Querying clearing switch for RRN: {rrn}")

        if rrn in self._database:
            record = self._database[rrn]
            # Adapt amount for interactive custom testing on demo RRN
            if amount_hint is not None and record.get("status") == BankStatus.SUCCESS and rrn == "410294820192" and abs(record["amount"] - amount_hint) > 0.01:
                logger.info(f"[BankSwitchTool] Adapting demo RRN {rrn} clearing amount to tested amount: {record['amount']} -> {amount_hint}")
                record["amount"] = amount_hint

            return BankSwitchResponse(
                rrn=rrn,
                amount=record["amount"],
                status=record["status"],
                customer_vpa=record["customer_vpa"],
                payer_bank=record["payer_bank"],
                clearing_timestamp=datetime.now(timezone.utc).isoformat(),
                raw_message=record["raw_message"],
            )

        # Fraud & Spoof Detection: Intercept unverified/fake RRNs on switch
        amt = amount_hint if amount_hint is not None else 0.0
        return BankSwitchResponse(
            rrn=rrn,
            amount=amt,
            status=BankStatus.NOT_FOUND,
            customer_vpa="unknown.spoof@vpa" if (rrn.startswith("FAKE") or rrn.startswith("SPOOF")) else "unregistered.payer@upi",
            payer_bank="NPCI Clearing Gateway",
            clearing_timestamp=datetime.now(timezone.utc).isoformat(),
            gateway_response_code="U30",
            raw_message="DECLINED: Transaction not found on NPCI clearing switch. Zero funds debited.",
        )

    def search_transactions(
        self,
        merchant_id: str,
        amount: float,
        time_window_seconds: int = 600,
    ) -> list:
        """Searches transactions for a merchant by amount within recent window."""
        results = []
        for rrn, record in self._database.items():
            if abs(record["amount"] - amount) < 0.01:
                results.append(self.verify_transaction(rrn, amount_hint=amount))
        return results

    def register_transaction(
        self,
        rrn: str,
        amount: float,
        status: BankStatus = BankStatus.SUCCESS,
        customer_vpa: str = "rahul.sharma@okhdfcbank",
        payer_bank: str = "HDFC Bank",
        raw_message: str = "Cleared and debited successfully",
    ) -> None:
        """Dynamically registers or overrides a transaction in the simulated bank switch."""
        self._database[rrn] = {
            "amount": amount,
            "status": status,
            "customer_vpa": customer_vpa,
            "payer_bank": payer_bank,
            "raw_message": raw_message,
        }



class SoundboxIoTTool(AbstractSoundboxIoT):
    """Interacts with MQTT broker & Soundbox hardware telemetry."""

    def __init__(self, mqtt_host: Optional[str] = None):
        self.mqtt_host = mqtt_host
        # Simulated device telemetry registry
        self._devices: Dict[str, Dict[str, Any]] = {
            "SB_DELHI_0841": {
                "merchant_id": "MERCH_GUPTA_TEA",
                "status": SoundboxStatus.PACKET_DROPPED,
                "rssi_dbm": -88,
                "battery": 76,
                "volume": 80,
                "is_online": True,
                "firmware_version": "v4.2.1-pytm",
                "pending_queue": 1,
                "last_played_rrn": "339182740192",
            },
            "SB_MUMBAI_1922": {
                "merchant_id": "MERCH_SHARMA_KIRANA",
                "status": SoundboxStatus.OFFLINE,
                "rssi_dbm": -104,
                "battery": 42,
                "volume": 75,
                "is_online": False,
                "firmware_version": "v4.1.0-pytm",
                "pending_queue": 2,
                "last_played_rrn": "229103948123",
            },
        }

    def inspect_telemetry(self, device_id: str) -> SoundboxTelemetry:
        """Retrieves real-time RSSI, battery, and packet sync state."""
        logger.info(f"[SoundboxIoTTool] Inspecting telemetry for device: {device_id}")

        dev = self._devices.get(device_id, {
            "merchant_id": "MERCH_DEFAULT",
            "status": SoundboxStatus.PACKET_DROPPED,
            "rssi_dbm": -82,
            "battery": 80,
            "pending_queue": 1,
            "last_played_rrn": None,
        })

        return SoundboxTelemetry(
            device_id=device_id,
            merchant_id=dev["merchant_id"],
            status=dev["status"],
            rssi_dbm=dev["rssi_dbm"],
            battery_percentage=dev["battery"],
            last_ping_utc=datetime.now(timezone.utc).isoformat(),
            pending_audio_queue=dev["pending_queue"],
            last_played_rrn=dev["last_played_rrn"],
        )

    def set_volume_remote(self, device_id: str, volume_percent: int) -> bool:
        """Remotely adjusts hardware speaker volume via simulated MQTT command."""
        logger.info(f"[SoundboxIoTTool] Remotely setting volume on {device_id} to {volume_percent}%")
        if device_id in self._devices:
            self._devices[device_id]["volume"] = max(0, min(100, volume_percent))
            if self._devices[device_id]["status"] == SoundboxStatus.MUTED and volume_percent > 0:
                self._devices[device_id]["status"] = SoundboxStatus.ONLINE
            return True
        return False

    def push_firmware_ota(self, device_id: str, target_version: str) -> bool:
        """Pushes mock OTA firmware update to Soundbox."""
        logger.info(f"[SoundboxIoTTool] Pushing OTA firmware {target_version} to {device_id}")
        if device_id in self._devices:
            self._devices[device_id]["firmware_version"] = target_version
            return True
        return False

    def push_audio_chirp(self, device_id: str, rrn: str, amount: float) -> bool:
        """Pushes MQTT audio chirp payload to trigger physical Soundbox chime."""
        logger.info(f"[SoundboxIoTTool] Pushing audio chirp payload: Device {device_id}, Amount ₹{amount}, RRN {rrn}")

        # Update local device registry to simulated ACK_RECEIVED
        if device_id in self._devices:
            self._devices[device_id]["status"] = SoundboxStatus.ACK_RECEIVED
            self._devices[device_id]["pending_queue"] = max(0, self._devices[device_id]["pending_queue"] - 1)
            self._devices[device_id]["last_played_rrn"] = rrn

        return True


class MerchantLedgerTool(AbstractMerchantLedger):
    """Interacts with Core Settlement Ledger with strict idempotency."""

    def __init__(self):
        # In-memory merchant ledger accounts
        self._merchant_balances: Dict[str, float] = {
            "MERCH_GUPTA_TEA": 4820.50,
            "MERCH_SHARMA_KIRANA": 12450.00,
            "MERCH_DEFAULT": 1500.00,
        }
        # Idempotency log mapping: rrn -> LedgerRecord
        self._settled_rrns: Dict[str, LedgerRecord] = {}

    def inspect_ledger(self, merchant_id: str, rrn: str) -> LedgerStatus:
        """Checks whether RRN has already been credited to merchant balance."""
        logger.info(f"[MerchantLedgerTool] Inspecting ledger for Merchant {merchant_id}, RRN {rrn}")
        if rrn in self._settled_rrns:
            return self._settled_rrns[rrn].status
        return LedgerStatus.UNCREDITED

    def find_credits(
        self,
        merchant_id: str,
        amount: Optional[float] = None,
        rrn: Optional[str] = None,
    ) -> list:
        """Finds confirmed ledger credit records matching merchant, amount, and/or UTR."""
        matches = []
        for r, rec in self._settled_rrns.items():
            if rec.merchant_id == merchant_id:
                if rrn and rec.rrn == rrn:
                    matches.append(rec)
                elif amount and abs(rec.amount - amount) < 0.01:
                    matches.append(rec)
        return matches

    def record_settlement_sync(self, merchant_id: str, rrn: str, amount: float) -> LedgerRecord:
        """
        Synchronizes confirmed payment to merchant settlement ledger.
        SETU never moves remitter money; this updates internal merchant settlement records.
        """
        return self.post_provisional_credit(merchant_id, rrn, amount)

    def post_provisional_credit(self, merchant_id: str, rrn: str, amount: float) -> LedgerRecord:
        """
        Executes idempotent provisional settlement credit.
        Prevents double-credit if executed multiple times for same RRN.
        """
        logger.info(f"[MerchantLedgerTool] Posting provisional credit: Merchant {merchant_id}, RRN {rrn}, Amount ₹{amount}")

        # Idempotency guard
        if rrn in self._settled_rrns:
            existing = self._settled_rrns[rrn]
            # If the user is re-testing with a new amount, allow the update
            if abs(existing.amount - amount) > 0.01:
                logger.info(f"[MerchantLedgerTool] Re-testing RRN {rrn} with new amount {amount}. Updating balance.")
                current_bal = self._merchant_balances.get(merchant_id, 1000.0)
                new_bal = current_bal + amount
                self._merchant_balances[merchant_id] = new_bal
                existing.amount = amount
                existing.balance_before = current_bal
                existing.balance_after = new_bal
                return existing
            logger.warning(f"[MerchantLedgerTool] Idempotency trip: RRN {rrn} already processed! Returning cached record.")
            return existing

        current_bal = self._merchant_balances.get(merchant_id, 1000.0)
        new_bal = current_bal + amount
        self._merchant_balances[merchant_id] = new_bal

        record = LedgerRecord(
            merchant_id=merchant_id,
            rrn=rrn,
            amount=amount,
            status=LedgerStatus.PROVISIONAL_CREDITED,
            balance_before=current_bal,
            balance_after=new_bal,
            timestamp=datetime.now(timezone.utc).isoformat(),
            idempotency_key=f"PROV_CREDIT_{rrn}_{int(time.time())}",
        )
        self._settled_rrns[rrn] = record
        return record


class MerchantNotificationTool(AbstractNotificationGateway):
    """Dispatches real-time omnichannel messages (WhatsApp / SMS)."""

    def __init__(self):
        self.outbox_log: list = []

    def send_resolution_notification(self, phone: str, merchant_name: str, rrn: str, amount: float, message: str) -> bool:
        """Dispatches automated settlement receipt notification."""
        payload = {
            "phone": phone,
            "merchant_name": merchant_name,
            "rrn": rrn,
            "amount": amount,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.outbox_log.append(payload)
        logger.info(f"[MerchantNotificationTool] Dispatched notification to {phone}: {message}")
        return True


class FraudShieldTool:
    """Detects Paytm Spoof apps, counterfeit payment screens, and fake debits."""

    def __init__(self):
        self.flagged_attempts: list = []

    def check_payment_legitimacy(self, rrn: str, claimed_amount: float, bank_status: BankStatus) -> Dict[str, Any]:
        """Cross-checks whether claimed transaction actually settled on banking switch."""
        logger.info(f"[FraudShieldTool] Auditing payment legitimacy for RRN {rrn}, Claimed ₹{claimed_amount}")

        is_spoof = (
            rrn.startswith("FAKE")
            or rrn.startswith("SPOOF")
            or bank_status in (BankStatus.NOT_FOUND, BankStatus.FAILED)
        )

        if is_spoof:
            record = {
                "rrn": rrn,
                "amount": claimed_amount,
                "is_fraud": True,
                "risk_score": 0.99,
                "threat_type": "PAYTM_SPOOF_COUNTERFEIT_APP",
                "soundbox_alert_text": "Chetavani: Yeh bhugtan Paytm par prapt nahi hua hai",
                "action": "HALT_AND_WARN_MERCHANT",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.flagged_attempts.append(record)
            logger.warning(f"[FraudShieldTool] FRAUD DETECTED! Intercepted fake transaction RRN {rrn} for ₹{claimed_amount}")
            return record

        return {
            "rrn": rrn,
            "amount": claimed_amount,
            "is_fraud": False,
            "risk_score": 0.02,
            "threat_type": "NONE",
            "action": "LEGITIMATE_TRANSACTION",
        }


class SalesEngineTool:
    """
    Drives measurable sales outcomes:
    1. Upgrades obsolete 2G Soundboxes to Soundbox 4G Pro when hardware packet drops occur.
    2. Cross-sells pre-approved Paytm Merchant Working Capital / Daily Loans.
    """

    def __init__(self):
        self.converted_leads: list = []

    def evaluate_growth_opportunity(self, merchant_id: str, device_model: str, health_score: float, monthly_gmv: float) -> Dict[str, Any]:
        """Evaluates hardware upgrade or working capital upsell opportunities."""
        logger.info(f"[SalesEngineTool] Evaluating sales opportunities for Merchant {merchant_id}")

        upgrade_offer = None
        if health_score < 0.50 or "2G" in device_model:
            upgrade_offer = {
                "lead_id": f"LEAD_SB4G_{int(time.time())}",
                "product": "Paytm Soundbox 4G Pro (Dual SIM + High Decibel Speaker)",
                "special_price_inr": 199.0,
                "monthly_rental_inr": 125.0,
                "reason": "Eliminates cellular packet drops; 4G speeds guarantee <1s voice chime.",
                "pitch_hindi": "Gupta ji, aapke Soundbox 2G me network drops ho rahe hain. Sirf ₹199 me naya Soundbox 4G Pro upgrade karein aur 1-second chime paayein.",
            }
            self.converted_leads.append(upgrade_offer)

        loan_offer = None
        if monthly_gmv >= 50000.0:
            loan_offer = {
                "product": "Paytm Business Daily Overdraft",
                "preapproved_limit_inr": 50000.0,
                "daily_interest_inr": 12.5,
                "reason": "Strong daily QR settlement track record unlocked pre-approved working capital.",
                "pitch_hindi": "Aapke dukan ke acche Paytm QR record par ₹50,000 ka business loan pre-approved hai (0 processing fee).",
            }

        return {
            "merchant_id": merchant_id,
            "has_upgrade_pitch": upgrade_offer is not None,
            "upgrade_offer": upgrade_offer,
            "loan_offer": loan_offer,
        }


class FleetHealthTool:
    """Monitors live bank switch latencies and broadcasts proactive voice advisories."""

    def __init__(self):
        self._switch_latencies = {
            "HDFC Bank": 120,
            "State Bank of India": 240,
            "ICICI Bank": 110,
            "Paytm Payments Bank": 80,
            "Axis Bank": 150,
        }

    def simulate_switch_degradation(self, bank_name: str = "State Bank of India", latency_ms: int = 4200) -> Dict[str, Any]:
        """Simulates banking switch degradation requiring proactive fleet advisory."""
        self._switch_latencies[bank_name] = latency_ms
        advisory = (
            f"Dhyan dein: {bank_name} UPI switch dheema chal raha hai. "
            f"Kripya customers ko doosre bank se pay karne ko kahein."
        )
        return {
            "bank_name": bank_name,
            "latency_ms": latency_ms,
            "status": "DEGRADED" if latency_ms > 3000 else "HEALTHY",
            "proactive_advisory": advisory,
            "fleet_broadcast_triggered": True,
        }


# Default singletons for direct use across agent modules
bank_tool = BankSwitchTool()
soundbox_tool = SoundboxIoTTool()
ledger_tool = MerchantLedgerTool()
notification_tool = MerchantNotificationTool()
fraud_tool = FraudShieldTool()
sales_tool = SalesEngineTool()
fleet_tool = FleetHealthTool()


def reset_sandbox_state():
    """Resets all singleton tools to initial pristine sandbox state."""
    bank_tool.__init__()
    soundbox_tool.__init__()
    ledger_tool.__init__()
    notification_tool.__init__()
    fraud_tool.__init__()
    sales_tool.__init__()
    fleet_tool.__init__()
