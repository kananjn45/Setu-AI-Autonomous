"""
SETTLE.AI - Indic Voice & Ingestion Package (Dev 3)
Exports STT recognizer, NLU entity extractor, Soundbox TTS synthesizer, and Voice Gateway.
"""

from settle_ai.voice.stt_service import IndicSpeechRecognizer, stt_recognizer
from settle_ai.voice.tts_service import SoundboxVoiceSynthesizer, tts_synthesizer
from settle_ai.voice.nlu_extractor import MerchantGrievanceExtractor, nlu_extractor
from settle_ai.voice.voice_gateway import VoiceIngestionGateway, voice_gateway

__all__ = [
    "IndicSpeechRecognizer",
    "stt_recognizer",
    "SoundboxVoiceSynthesizer",
    "tts_synthesizer",
    "MerchantGrievanceExtractor",
    "nlu_extractor",
    "VoiceIngestionGateway",
    "voice_gateway",
]
