"""
SETTLE.AI - Abstract Interfaces for External Systems
Defines abstract contracts for:
1. Bank Switch / NPCI Gateway
2. Core Merchant CBS Ledger
3. Soundbox MQTT Hardware Broker
4. Omnichannel Notification Gateway
Ensures all mock systems can be seamlessly swapped for real production APIs.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from settle_ai.agent.schemas import (
    BankSwitchResponse,
    SoundboxTelemetry,
    LedgerRecord,
    LedgerStatus,
)


class AbstractBankSwitch(ABC):
    """Interface for NPCI UPI clearing switch & acquiring banking gateway."""

    @abstractmethod
    def verify_transaction(self, rrn: str, amount_hint: Optional[float] = None) -> BankSwitchResponse:
        """Queries clearing switch for exact 12-digit RRN."""
        pass

    @abstractmethod
    def search_transactions(
        self,
        merchant_id: str,
        amount: float,
        time_window_seconds: int = 600,
    ) -> List[BankSwitchResponse]:
        """Searches transactions for a merchant by amount within a recent time window."""
        pass


class AbstractMerchantLedger(ABC):
    """Interface for Core Settlement Ledger (CBS double-entry bookkeeping)."""

    @abstractmethod
    def inspect_ledger(self, merchant_id: str, rrn: str) -> LedgerStatus:
        """Checks if RRN has already been credited to merchant balance."""
        pass

    @abstractmethod
    def find_credits(
        self,
        merchant_id: str,
        amount: Optional[float] = None,
        rrn: Optional[str] = None,
    ) -> List[LedgerRecord]:
        """Finds confirmed ledger credit records matching merchant, amount, and/or UTR."""
        pass

    @abstractmethod
    def record_settlement_sync(
        self,
        merchant_id: str,
        rrn: str,
        amount: float,
    ) -> LedgerRecord:
        """
        Synchronizes confirmed payment to merchant settlement ledger.
        Note: SETU never moves remitter money; this updates internal merchant settlement records.
        """
        pass


class AbstractSoundboxIoT(ABC):
    """Interface for MQTT broker & Soundbox hardware telemetry gateway."""

    @abstractmethod
    def inspect_telemetry(self, device_id: str) -> SoundboxTelemetry:
        """Retrieves real-time RSSI, battery, volume, and heartbeat status."""
        pass

    @abstractmethod
    def push_audio_chirp(self, device_id: str, rrn: str, amount: float) -> bool:
        """Dispatches MQTT payload to trigger physical audio broadcast on device."""
        pass

    @abstractmethod
    def set_volume_remote(self, device_id: str, volume_percent: int) -> bool:
        """Remotely adjusts hardware speaker volume via MQTT command."""
        pass

    @abstractmethod
    def push_firmware_ota(self, device_id: str, target_version: str) -> bool:
        """Triggers remote OTA firmware update."""
        pass


class AbstractNotificationGateway(ABC):
    """Interface for real-time merchant messaging (WhatsApp / SMS)."""

    @abstractmethod
    def send_resolution_notification(
        self,
        phone: str,
        merchant_name: str,
        rrn: str,
        amount: float,
        message: str,
    ) -> bool:
        """Dispatches resolution receipt or fraud security advisory."""
        pass
