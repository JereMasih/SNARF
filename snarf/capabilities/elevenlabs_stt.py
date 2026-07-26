import os

import requests

from snarf.capabilities.base import Capability

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
        response.raise_for_status()
        return response.json()["text"]
