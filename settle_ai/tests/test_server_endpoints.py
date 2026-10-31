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


def test_hitl_reject_endpoint():
    """Tests synchronous rejection of an escalated dispute by operations supervisor."""
    from settle_ai.server import reject_hitl_api, HitlRejectRequest, handle_whatsapp_message, WhatsAppMessageRequest

    # Create escalated dispute first
    req = WhatsAppMessageRequest(
        message_text="Sharma Kirana 15000 hold RRN 883920194821",
        merchant_name="Sharma Kirana Store",
        merchant_id="MERCH_SHARMA_KIRANA",
        device_id="SB_MUMBAI_0112",
        amount_hint=15000.0,
        rrn_hint="883920194821",
    )
    res = handle_whatsapp_message(req)
    disp_id = res["dispute_id"]

    reject_req = HitlRejectRequest(
        dispute_id=disp_id,
        supervisor_notes="Claim audited: customer cancelled order at counter. Dispute rejected.",
    )
    rej_res = reject_hitl_api(reject_req)

    assert rej_res["status"] == "REJECTED_BY_SUPERVISOR"
    assert rej_res["agent_state"]["hitl_approved"] is False
    assert rej_res["agent_state"]["ledger_credited"] is False
    assert "DISPUTE REJECTED" in rej_res["message"]


def test_whatsapp_fake_payment_intercepted():
    """Verifies that fake payment queries via WhatsApp trigger fraud shield without ledger credit."""
    from settle_ai.server import handle_whatsapp_message, WhatsAppMessageRequest

    req = WhatsAppMessageRequest(
        message_text="Customer ne fake paytm screenshot dikhaya 400 rupaye ka RRN FAKE_991122",
        amount_hint=400.0,
        rrn_hint="FAKE_991122",
    )
    res = handle_whatsapp_message(req)

    assert res["fraud_detected"] is True
    assert res["is_settled"] is False
    assert res["agent_state"]["ledger_credited"] is False
    assert "Fake Payment Intercepted" in res["reply_text"]
    assert res["digital_receipt"]["status"] == "BLOCKED_FRAUD_INTERCEPTED"
    # Audio alarm checks: MUST be security alarm, NEVER 'prapt hue'
    assert res["soundbox_audio"] is not None
    assert res["soundbox_audio"].get("is_fraud_alarm") is True
    assert "prapt hue" not in res["soundbox_audio"]["text"]
    assert res["soundbox_audio"]["byte_size"] > 10000


def test_whatsapp_user_10000_query_escalated_and_rejected():
    """Verifies that an arbitrary amount > 5000 (e.g. 10000) from Hindi text dynamically scales and rejects."""
    from settle_ai.server import handle_whatsapp_message, WhatsAppMessageRequest, reject_hitl_api, HitlRejectRequest

    req = WhatsAppMessageRequest(
        message_text="user ne 10000 daale per aaye nhi",
        merchant_name="Gupta Tea Stall",
        merchant_id="MERCH_GUPTA_TEA",
    )
    res = handle_whatsapp_message(req)

    assert res["amount"] == 10000.0
    assert res["hitl_tripped"] is True
    assert res["is_settled"] is False

    # Operations supervisor rejects the claim
    rej_res = reject_hitl_api(HitlRejectRequest(
        dispute_id=res["dispute_id"],
        supervisor_notes="Discrepancy confirmed: zero debit at issuing bank.",
    ))

    assert rej_res["status"] == "REJECTED_BY_SUPERVISOR"
    assert rej_res["agent_state"]["amount"] == 10000.0  # Dynamic amount preserved!
    assert rej_res["agent_state"]["hitl_approved"] is False
    assert rej_res["agent_state"]["ledger_credited"] is False

