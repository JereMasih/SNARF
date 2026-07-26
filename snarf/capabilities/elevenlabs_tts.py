import os

import requests

from snarf.capabilities.base import Capability

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_MODEL = "eleven_multilingual_v2"


class ElevenLabsTTS(Capability):
    name = "elevenlabs_tts"

    def __init__(self):
        self._api_key = os.environ.get("ELEVENLABS_API_KEY")
        self._voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._voice_id)

    def synthesize(self, text: str) -> bytes:
        if not self.available:
            raise RuntimeError(
                "ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID no configuradas (ver .env.example)."
            )
        response = requests.post(
            API_URL.format(voice_id=self._voice_id),
            headers={"xi-api-key": self._api_key},
            json={"text": text, "model_id": DEFAULT_MODEL},
            timeout=30,
        )
        response.raise_for_status()
        return response.content
