"""
SETTLE.AI - Indic Speech Recognizer (Sarvam AI Saaras STT)
Transcribes merchant vernacular voice grievances (Hindi, Hinglish, regional dialects).
"""

import os
import io
import logging
from typing import Optional, Union, Dict, Any
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
logger = logging.getLogger("settle_ai.voice.stt")


class IndicSpeechRecognizer:
    """Transcribes merchant voice grievances using Sarvam AI Saaras STT."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        self.client: Optional[SarvamAI] = None
        if self.api_key:
            try:
                self.client = SarvamAI(api_subscription_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize SarvamAI client: {e}")

    def transcribe_audio(
        self,
        audio_source: Union[str, bytes, io.BytesIO],
        language_code: str = "hi-IN",
        model: str = "saaras:v3",
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribes speech audio into text.
        audio_source can be a file path string, raw audio bytes, or a BytesIO buffer.
        """
        logger.info(f"[IndicSTT] Transcribing audio with Sarvam Saaras (Language: {language_code})")

        if not self.client:
            raise ValueError("SarvamAI client not initialized. Ensure SARVAM_API_KEY is configured.")

        # Prepare file payload
        file_tuple = None
        if isinstance(audio_source, str):
            if not os.path.exists(audio_source):
                raise FileNotFoundError(f"Audio file not found: {audio_source}")
            with open(audio_source, "rb") as f:
                content = f.read()
            fname = filename or os.path.basename(audio_source)
            ctype = content_type or ("audio/webm" if fname.endswith(".webm") else "audio/wav")
            file_tuple = (fname, content, ctype)
        elif isinstance(audio_source, bytes):
            fname = filename or "audio.wav"
            ctype = content_type or ("audio/webm" if fname.endswith(".webm") else "audio/wav")
            file_tuple = (fname, audio_source, ctype)
        elif isinstance(audio_source, io.BytesIO):
            fname = filename or "audio.wav"
            ctype = content_type or ("audio/webm" if fname.endswith(".webm") else "audio/wav")
            file_tuple = (fname, audio_source.getvalue(), ctype)
        else:
            raise ValueError(f"Unsupported audio source type: {type(audio_source)}")

        try:
            response = self.client.speech_to_text.transcribe(
                file=file_tuple,
                model=model,
                language_code=language_code,
            )
            transcript = response.transcript.strip()
            logger.info(f"[IndicSTT] Transcription succeeded: '{transcript}'")
            return {
                "transcript": transcript,
                "language_code": response.language_code or language_code,
                "request_id": response.request_id,
            }
        except Exception as e:
            logger.error(f"[IndicSTT] Sarvam STT transcription failed: {e}")
            raise e


# Default singleton instance
stt_recognizer = IndicSpeechRecognizer()
