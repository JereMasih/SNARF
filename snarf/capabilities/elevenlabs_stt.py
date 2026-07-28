import os

import requests

from snarf.capabilities.base import Capability
from snarf.telemetry import usage_tracker

API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v1"


class ElevenLabsSTT(Capability):
    name = "elevenlabs_stt"

    def __init__(self):
        self._api_key = os.environ.get("ELEVENLABS_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if not self.available:
            raise RuntimeError("ELEVENLABS_API_KEY no configurada (ver .env.example).")
        response = requests.post(
            API_URL,
            headers={"xi-api-key": self._api_key},
            data={"model_id": DEFAULT_MODEL},
            files={"file": (filename, audio_bytes)},
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"ElevenLabs STT {response.status_code}: {response.text}")
        payload = response.json()
        usage_tracker.record_elevenlabs_stt_call(self._duration_seconds(payload))
        return payload["text"]

    @staticmethod
    def _duration_seconds(payload: dict) -> float | None:
        # La respuesta no trae una duración explícita, pero sí timestamps por
        # palabra; el "end" de la última palabra es la mejor aproximación
        # disponible sin decodificar el audio nosotros mismos.
        words = payload.get("words")
        if not words:
            return None
        last_end = words[-1].get("end")
        return float(last_end) if last_end is not None else None
