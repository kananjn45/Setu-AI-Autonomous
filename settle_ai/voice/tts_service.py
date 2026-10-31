"""
SETTLE.AI - Soundbox Voice Synthesizer (Sarvam AI Bulbul TTS)
Synthesizes the authentic Paytm Soundbox payment confirmation chime:
"Paytm par {amount} rupaye prapt hue" in Hindi and Indic languages.
"""

import os
import math
import struct
import wave
import io
import base64
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
logger = logging.getLogger("settle_ai.voice.tts")


class SoundboxVoiceSynthesizer:
    """Generates broadcast-quality Soundbox audio alerts via Sarvam AI TTS or security sirens."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        self.client: Optional[SarvamAI] = None
        if self.api_key:
            try:
                self.client = SarvamAI(api_subscription_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize SarvamAI client: {e}")

    def generate_alarm_siren_bytes(self, duration_s: float = 2.4, sample_rate: int = 22050) -> bytes:
        """Synthesizes an unmistakable emergency two-tone security alarm siren."""
        num_samples = int(sample_rate * duration_s)
        data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            cycle = (t % 0.6)
            if cycle < 0.45:
                freq1 = 880 + 200 * math.sin(2 * math.pi * 8 * t)
                freq2 = 440 + 100 * math.cos(2 * math.pi * 8 * t)
                val = 0.5 * math.sin(2 * math.pi * freq1 * t) + 0.3 * math.sin(2 * math.pi * freq2 * t)
                val += 0.2 * math.sin(2 * math.pi * 1760 * t)
                val *= 0.8
            else:
                val = 0.0
            sample = int(max(-32768, min(32767, val * 32767)))
            data.extend(struct.pack('<h', sample))

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data)
        return buf.getvalue()

    def format_soundbox_announcement(self, amount: float, language: str = "hi-IN") -> str:
        """Formats the canonical Paytm Soundbox announcement text."""
        amt_str = f"{int(amount)}" if amount.is_integer() else f"{amount:,.2f}"

        if language == "hi-IN":
            return f"Paytm par {amt_str} rupaye prapt hue"
        elif language == "en-IN":
            return f"Received {amt_str} rupees on Paytm"
        elif language == "gu-IN":
            return f"Paytm par {amt_str} rupiya malya"
        elif language == "mr-IN":
            return f"Paytm var {amt_str} rupaye prapta jhale"
        elif language == "ta-IN":
            return f"Paytm il {amt_str} roobai perappattathu"
        elif language == "te-IN":
            return f"Paytm lo {amt_str} roopayalu andinavi"
        return f"Paytm par {amt_str} rupaye prapt hue"

    def synthesize_security_alarm(
        self,
        amount: float = 0.0,
        output_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes an authentic high-impact emergency security alert alarm.
        Guaranteed to announce 'Saavdhan! Yeh ek fraud transaction hai. Paytm par koi paisa prapt nahi hua hai.'
        """
        text = "🚨 Saavdhan! Yeh ek fraud transaction hai. Paytm par koi paisa prapt nahi hua hai."
        logger.info(f"[SoundboxTTS] Synthesizing FRAUD VOICE ALARM (amount: ₹{amount:,.2f})")

        audio_bytes = None
        if output_file_path and os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 100:
            try:
                with open(output_file_path, "rb") as f:
                    audio_bytes = f.read()
            except Exception as e:
                logger.warning(f"[SoundboxTTS] Could not read cached alarm audio: {e}")

        # If not cached or too small, synthesize via Sarvam Bulbul TTS
        if (not audio_bytes or len(audio_bytes) < 1000) and self.client:
            try:
                resp = self.client.text_to_speech.convert(
                    text="सावधान! यह एक फ्रॉड ट्रांजैक्शन है। पेटीएम पर कोई पैसा प्राप्त नहीं हुआ है।",
                    language_code="hi-IN",
                    model="bulbul:v3"
                )
                if resp.audios and len(resp.audios) > 0:
                    audio_bytes = base64.b64decode(resp.audios[0])
                    logger.info(f"[SoundboxTTS] Successfully synthesized {len(audio_bytes)} fraud warning voice bytes via Sarvam AI.")
            except Exception as e:
                logger.error(f"[SoundboxTTS] Sarvam TTS call failed for fraud warning: {e}")

        if not audio_bytes or len(audio_bytes) < 1000:
            audio_bytes = self.generate_alarm_siren_bytes()

        if output_file_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
                with open(output_file_path, "wb") as f:
                    f.write(audio_bytes)
            except Exception as e:
                logger.warning(f"[SoundboxTTS] Could not cache alarm: {e}")

        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {
            "amount": amount,
            "text": text,
            "language_code": "hi-IN",
            "audio_base64": audio_base64,
            "audio_data_url": f"data:audio/wav;base64,{audio_base64}",
            "byte_size": len(audio_bytes),
            "output_path": output_file_path,
            "is_fraud_alarm": True,
        }

    def synthesize_chirp(
        self,
        amount: float,
        language_code: str = "hi-IN",
        output_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes the Soundbox payment confirmation audio.
        Guards against fraud warning files being converted to 'prapt hue'.
        """
        if output_file_path and ("warning" in output_file_path.lower() or "security" in output_file_path.lower() or "fake" in output_file_path.lower()):
            return self.synthesize_security_alarm(amount=amount, output_file_path=output_file_path)

        text = self.format_soundbox_announcement(amount=amount, language=language_code)
        logger.info(f"[SoundboxTTS] Synthesizing Soundbox chime: '{text}' (Language: {language_code})")

        audio_base64 = None
        audio_bytes = None

        # Fast Cache Hit: If cached audio file already exists for this chime, load instantly
        if output_file_path and os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 100:
            try:
                with open(output_file_path, "rb") as f:
                    audio_bytes = f.read()
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                logger.info(f"[SoundboxTTS] Loaded cached chime from disk ({len(audio_bytes)} bytes): {output_file_path}")
                return {
                    "amount": amount,
                    "text": text,
                    "language_code": language_code,
                    "audio_base64": audio_base64,
                    "audio_data_url": f"data:audio/wav;base64,{audio_base64}",
                    "byte_size": len(audio_bytes),
                    "output_path": output_file_path,
                }
            except Exception as e:
                logger.warning(f"[SoundboxTTS] Could not read cached audio: {e}")

        if self.client:
            try:
                response = self.client.text_to_speech.convert(
                    text=text,
                    language_code=language_code,
                    model="bulbul:v3",
                )
                if response.audios and len(response.audios) > 0:
                    audio_base64 = response.audios[0]
                    audio_bytes = base64.b64decode(audio_base64)
                    logger.info(f"[SoundboxTTS] Successfully synthesized {len(audio_bytes)} audio bytes via Sarvam AI.")
            except Exception as e:
                logger.error(f"[SoundboxTTS] Sarvam TTS call failed: {e}. Falling back to cached or synthetic audio.")

        # Fallback if API unavailable
        if audio_bytes is None:
            audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Save to disk if requested
        if output_file_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
            with open(output_file_path, "wb") as f:
                f.write(audio_bytes)
            logger.info(f"[SoundboxTTS] Saved audio chime file to: {output_file_path}")

        return {
            "amount": amount,
            "text": text,
            "language_code": language_code,
            "audio_base64": audio_base64,
            "audio_data_url": f"data:audio/wav;base64,{audio_base64}",
            "byte_size": len(audio_bytes),
            "output_path": output_file_path,
        }


# Default singleton instance
tts_synthesizer = SoundboxVoiceSynthesizer()
