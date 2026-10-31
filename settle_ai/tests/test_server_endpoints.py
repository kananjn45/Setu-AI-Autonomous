"""
Tests for SETU Server Endpoints:
1. Customer QR Payment Simulator (Checkpoint 1)
2. System State & KPI Retrieval
3. Inbound WhatsApp Grievance Settlement & Receipts
"""

import asyncio
import pytest
from settle_ai.server import (
    simulate_customer_pay,
    CustomerPayRequest,
    get_system_state,
    handle_whatsapp_message,
    WhatsAppMessageRequest,
    get_teammate_kpis,
)
from settle_ai.agent.tools import reset_sandbox_state


@pytest.fixture(autouse=True)
def clean_sandbox():
    reset_sandbox_state()
    yield


def test_customer_pay_simulation_endpoint():
    """Verifies Checkpoint 1 simulated QR payment and hardware drop."""
    req = CustomerPayRequest(amount=350.0, rrn="410294820192")
    data = simulate_customer_pay(req)

    assert data["status"] == "CUSTOMER_DEBITED_SOUNDBOX_DROPPED"
    assert data["rrn"] == "410294820192"
    assert data["soundbox_status"] == "PACKET_DROPPED"
    assert "Soundbox" in data["suggested_query"]


def test_system_state_endpoint():
    """Verifies system state and balance retrieval."""
    data = get_system_state()
    assert "ledger_balances" in data
    assert "soundbox_devices" in data


def test_teammate_kpis_endpoint():
    """Verifies SETU measurable outcome KPIs."""
    data = get_teammate_kpis()
    assert data["teammate_id"] == "SETU-AGT-01"
    assert data["customer_service"]["deflection_rate_pct"] > 80.0
    assert data["fraud_defense"]["spoof_attempts_intercepted"] >= 14
    assert data["sales_growth"]["device_upgrades_initiated"] >= 23


def test_whatsapp_message_autonomous_settle():
    """Verifies inbound WhatsApp grievance settlement and digital receipt generation."""
    req = WhatsAppMessageRequest(
        phone="+919811223344",
        merchant_name="Gupta Tea Stall",
        message_text="Bhaiya 400 rupaye kata par Soundbox nahi bola. RRN number hai 410294820192",
        amount_hint=400.0,
        rrn_hint="410294820192",
    )
    data = handle_whatsapp_message(req)

    assert data["status"] == "SUCCESS"
    assert data["is_settled"] is True
    assert data["amount"] == 400.0
    assert "digital_receipt" in data
    assert data["digital_receipt"]["rrn"] == "410294820192"
    assert data["digital_receipt"]["sha256_audit_seal"] is not None
    assert "Paytm for Business" in data["reply_text"]


def test_whatsapp_message_high_value_circuit_breaker():
    """Verifies WhatsApp dispute halting on transactions >= INR 5,000."""
    req = WhatsAppMessageRequest(
        phone="+919822334455",
        merchant_name="Sharma Kirana Store",
        message_text="Order 15000 ruka hua hai RRN 883920194821",
        amount_hint=15000.0,
        rrn_hint="883920194821",
    )
    data = handle_whatsapp_message(req)

    assert data["hitl_tripped"] is True
    assert data["is_settled"] is False
    assert "exceeds the ₹5,000 autonomous threshold" in data["reply_text"]
