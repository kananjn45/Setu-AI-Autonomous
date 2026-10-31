"""
SETTLE.AI - Voice & Ingestion Test Suite (Dev 3)
Validates Sarvam AI TTS audio synthesis, Indic NLU entity extraction,
and end-to-end Voice Gateway integration with LangGraph.
"""

import os
import pytest
from settle_ai.voice.tts_service import SoundboxVoiceSynthesizer
from settle_ai.voice.nlu_extractor import MerchantGrievanceExtractor
from settle_ai.voice.voice_gateway import VoiceIngestionGateway
from settle_ai.agent.tools import reset_sandbox_state


@pytest.fixture(autouse=True)
def clean_sandbox():
    reset_sandbox_state()
    yield


def test_soundbox_tts_synthesis():
    """Validates Sarvam AI Bulbul TTS payment confirmation chime synthesis (with fallback)."""
    tts = SoundboxVoiceSynthesizer()
    chirp_data = tts.synthesize_chirp(amount=350.0, language_code="hi-IN")

    assert chirp_data["text"] == "Paytm par 350 rupaye prapt hue"
    assert chirp_data["audio_base64"] is not None
    assert chirp_data["byte_size"] >= 44, "Audio output is suspiciously small"
    assert chirp_data["audio_data_url"].startswith("data:audio/wav;base64,")
    print(f"\n[TTS VERIFIED] Synthesized: '{chirp_data['text']}' ({chirp_data['byte_size']} bytes)")


def test_nlu_entity_extraction_hindi():
    """Validates 12-digit RRN and transaction amount extraction from Hindi merchant grievance."""
    extractor = MerchantGrievanceExtractor()
    query = "Bhaiya humari dukan pe 350 rupaye kata par Soundbox nahi bola. RRN number hai 410294820192"

    result = extractor.extract_grievance_entities(query)
    assert result["rrn"] == "410294820192"
    assert result["amount"] == 350.0
    assert result["intent"] == "SOUNDBOX_SILENT"
    print(f"\n[NLU VERIFIED] Extracted RRN={result['rrn']}, Amount={result['amount']}, Intent={result['intent']}")


def test_voice_gateway_end_to_end_loop():
    """
    Validates the complete voice-to-chirp pipeline:
    Hindi Grievance -> NLU Extraction -> LangGraph Settle -> Soundbox Audio Chirp.
    """
    gateway = VoiceIngestionGateway()
    query = "Bhaiya 350 rupaye kata par Soundbox nahi bola RRN 410294820192"

    result = gateway.process_voice_grievance(
        audio_or_text=query,
        merchant_name="Gupta Tea Stall",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
    )

    assert result["status"] == "SETTLED"
    assert result["extracted_entities"]["rrn"] == "410294820192"
    assert result["extracted_entities"]["amount"] == 350.0
    assert result["soundbox_audio"] is not None
    assert result["soundbox_audio"]["text"] == "Paytm par 350 rupaye prapt hue"
    print(f"\n[VOICE GATEWAY SUCCESS] Total pipeline latency: {result['latencies_ms']['total']}ms")
    print(f"  -> Extracted: RRN {result['extracted_entities']['rrn']}, INR {result['extracted_entities']['amount']}")
    print(f"  -> Soundbox Chirp Generated: {result['soundbox_audio']['byte_size']} bytes")


def test_voice_gateway_high_value_circuit_breaker():
    """Validates that a high-value grievance (INR 15,000) halts before TTS chirp generation."""
    gateway = VoiceIngestionGateway()
    query = "Sharma Kirana Store ka 15,000 rupaye ruka hua hai RRN 883920194821"

    result = gateway.process_voice_grievance(
        audio_or_text=query,
        merchant_name="Sharma Kirana Store",
        merchant_id="MERCH_SHARMA_KIRANA",
        device_id="SB_DELHI_0841",
    )

    assert result["status"] == "HALTED_HITL"
    assert result["agent_state"].hitl_required is True
    # Soundbox audio should NOT be played for unauthorized high-value dispute
    assert result["soundbox_audio"] is None
    print("\n[SAFETY CIRCUIT BREAKER VERIFIED] High-value grievance halted before audio push.")


def test_nlu_spoken_hindi_phrases_400():
    """Validates Hindi spoken phrases extraction for custom 400 and variant amounts."""
    extractor = MerchantGrievanceExtractor()

    # User's exact spoken sentence from grievance audio
    res1 = extractor.extract_grievance_entities("maine jab usko bola ki 400 rupaye kate hain")
    assert res1["amount"] == 400.0

    res2 = extractor.extract_grievance_entities("400 rupaye kate hain")
    assert res2["amount"] == 400.0

    res3 = extractor.extract_grievance_entities("chaar sau rupaye kate hain")
    assert res3["amount"] == 400.0

    res4 = extractor.extract_grievance_entities("dedh sau rupaye kate hain")
    assert res4["amount"] == 150.0

    res5 = extractor.extract_grievance_entities("saadhe chaar sau rupaye")
    assert res5["amount"] == 450.0


def test_dynamic_amount_voice_settlement_400():
    """Validates complete voice gateway end-to-end resolution for 400 INR."""
    gateway = VoiceIngestionGateway()
    query = "maine jab usko bola ki 400 rupaye kate hain"

    result = gateway.process_voice_grievance(
        audio_or_text=query,
        merchant_name="Gupta Tea Stall",
        merchant_id="MERCH_GUPTA_TEA",
        device_id="SB_DELHI_0841",
    )

    assert result["status"] == "SETTLED"
    assert result["extracted_entities"]["amount"] == 400.0
    assert result["agent_state"].amount == 400.0
    assert result["soundbox_audio"] is not None
    assert result["soundbox_audio"]["text"] == "Paytm par 400 rupaye prapt hue"


if __name__ == "__main__":
    pytest.main(["-v", __file__])

