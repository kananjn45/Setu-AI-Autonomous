"""
SETTLE.AI - Voice Ingestion Gateway (Dev 3 -> Dev 1 Pipeline)
Integrates Sarvam STT -> Indic NLU -> LangGraph Orchestrator -> Sarvam TTS Chirp
"""

import time
import uuid
import logging
from typing import Optional, Union, Dict, Any
import io

from settle_ai.agent.schemas import DisputeGrievance, DisputeChannel, AgentState
from settle_ai.agent.orchestrator import orchestrator
from settle_ai.voice.stt_service import stt_recognizer
from settle_ai.voice.nlu_extractor import nlu_extractor
from settle_ai.voice.tts_service import tts_synthesizer

logger = logging.getLogger("settle_ai.voice.gateway")


class VoiceIngestionGateway:
    """End-to-end voice grievance gateway for Paytm merchants."""

    def __init__(self):
        self.stt = stt_recognizer
        self.nlu = nlu_extractor
        self.tts = tts_synthesizer
        self.orchestrator = orchestrator

    def process_voice_grievance(
        self,
        audio_or_text: Union[str, bytes, io.BytesIO],
        merchant_id: str = "MERCH_GUPTA_TEA",
        device_id: str = "SB_DELHI_0841",
        merchant_name: str = "Gupta Tea Stall",
        merchant_phone: str = "+919811223344",
        channel: DisputeChannel = DisputeChannel.INDIC_VOICE,
    ) -> Dict[str, Any]:
        """
        Executes complete voice pipeline:
        1. Transcribe voice memo (if audio)
        2. Extract RRN, Amount & Intent via NLU
        3. Trigger LangGraph Orchestrator
        4. Synthesize Soundbox chirp audio on resolution
        """
        t_start = time.time()
        logger.info(f"[VoiceGateway] Starting voice grievance processing for {merchant_name} ({merchant_id})")

        # Step 1: Speech-to-Text or direct transcript
        if isinstance(audio_or_text, str) and not (audio_or_text.endswith(".wav") or audio_or_text.endswith(".mp3")):
            transcript = audio_or_text
            stt_latency_ms = 0.0
        else:
            t0 = time.time()
            stt_result = self.stt.transcribe_audio(audio_source=audio_or_text)
            transcript = stt_result["transcript"]
            stt_latency_ms = round((time.time() - t0) * 1000, 2)

        # Step 2: Indic NLU Extraction
        t1 = time.time()
        entities = self.nlu.extract_grievance_entities(text=transcript)
        nlu_latency_ms = round((time.time() - t1) * 1000, 2)

        rrn = entities["rrn"]
        amount = entities["amount"]
        intent = entities["intent"]

        # Step 3: LangGraph Autonomous Settle Loop
        dispute_id = f"DSP_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        grievance = DisputeGrievance(
            dispute_id=dispute_id,
            merchant_id=merchant_id,
            device_id=device_id,
            rrn=rrn,
            amount=amount,
            voice_transcript=transcript,
            channel=channel,
            merchant_name=merchant_name,
            merchant_phone=merchant_phone,
        )

        t2 = time.time()
        agent_state: AgentState = self.orchestrator.resolve_dispute(grievance)
        agent_latency_ms = round((time.time() - t2) * 1000, 2)

        # Step 4: Soundbox Audio Chirp Synthesis
        chirp_audio_data = None
        tts_latency_ms = 0.0
        if agent_state.soundbox_pushed or (agent_state.is_completed and not agent_state.hitl_required):
            t3 = time.time()
            chirp_audio_data = self.tts.synthesize_chirp(amount=amount, language_code="hi-IN")
            tts_latency_ms = round((time.time() - t3) * 1000, 2)

        total_latency_ms = round((time.time() - t_start) * 1000, 2)

        return {
            "dispute_id": dispute_id,
            "transcript": transcript,
            "extracted_entities": {
                "rrn": rrn,
                "amount": amount,
                "intent": intent,
                "nlu_source": entities["source"],
            },
            "latencies_ms": {
                "stt": stt_latency_ms,
                "nlu": nlu_latency_ms,
                "agent_decision": agent_latency_ms,
                "soundbox_tts": tts_latency_ms,
                "total": total_latency_ms,
            },
            "agent_state": agent_state,
            "soundbox_audio": chirp_audio_data,
            "status": "SETTLED" if agent_state.is_completed else "HALTED_HITL",
            "message": agent_state.final_resolution_message,
        }


# Default singleton instance
voice_gateway = VoiceIngestionGateway()
