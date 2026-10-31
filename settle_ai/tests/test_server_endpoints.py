"""
Tests for SETTLE.AI Server Endpoints:
1. Customer QR Payment Simulator (Checkpoint 1)
2. Voice Audio Ingestion & STT Gateway (Checkpoint 2)
"""

import pytest
from fastapi.testclient import TestClient
from settle_ai.server import app

client = TestClient(app)


def test_customer_pay_simulation_endpoint():
    """Verifies Checkpoint 1 simulated QR payment and hardware drop."""
    response = client.post(
        "/api/simulator/customer-pay",
        json={"amount": 350.0, "rrn": "410294820192"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CUSTOMER_DEBITED_SOUNDBOX_DROPPED"
    assert data["rrn"] == "410294820192"
    assert data["soundbox_status"] == "PACKET_DROPPED"
    assert "Soundbox" in data["suggested_query"]


def test_system_state_endpoint():
    """Verifies system state and balance retrieval."""
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert "ledger_balances" in data
    assert "soundbox_devices" in data


def test_whatsapp_message_autonomous_settle():
    """Verifies inbound WhatsApp grievance settlement and digital receipt generation."""
    response = client.post(
        "/api/whatsapp/message",
        json={
            "phone": "+919811223344",
            "merchant_name": "Gupta Tea Stall",
            "message_text": "Bhaiya 400 rupaye kata par Soundbox nahi bola. RRN number hai 410294820192",
            "amount_hint": 400.0,
            "rrn_hint": "410294820192",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["is_settled"] is True
    assert data["amount"] == 400.0
    assert "digital_receipt" in data
    assert data["digital_receipt"]["rrn"] == "410294820192"
    assert data["digital_receipt"]["sha256_audit_seal"] is not None
    assert "Paytm for Business" in data["reply_text"]


def test_whatsapp_message_high_value_circuit_breaker():
    """Verifies WhatsApp dispute halting on transactions >= INR 5,000."""
    response = client.post(
        "/api/whatsapp/message",
        json={
            "phone": "+919822334455",
            "merchant_name": "Sharma Kirana Store",
            "message_text": "Order 15000 ruka hua hai RRN 883920194821",
            "amount_hint": 15000.0,
            "rrn_hint": "883920194821",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["hitl_tripped"] is True
    assert data["is_settled"] is False
    assert "exceeds the ₹5,000 autonomous threshold" in data["reply_text"]
