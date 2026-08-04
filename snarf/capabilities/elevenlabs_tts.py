import os

import requests

from snarf.capabilities.base import Capability
from snarf.telemetry import detail, usage_tracker

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
SUBSCRIPTION_URL = "https://api.elevenlabs.io/v1/user/subscription"
DEFAULT_MODEL = "eleven_turbo_v2_5"


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
        usage_tracker.record_elevenlabs_tts_call(len(text), detalle=detail.truncate_detalle(text))
        return response.content

    def subscription_info(self) -> dict:
        # El "gasto estimado" del panel de costo se calcula desde llamadas
        # trackeadas localmente — cargar crédito en la cuenta de ElevenLabs no
        # cambia nada ahí (no es un saldo real). Esto sí es el dato real de la
        # cuenta, consultado en vivo, no inventado.
        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY no configurada (ver .env.example).")
        response = requests.get(SUBSCRIPTION_URL, headers={"xi-api-key": self._api_key}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "tier": data.get("tier", ""),
            "character_count": data.get("character_count", 0),
            "character_limit": data.get("character_limit", 0),
            "next_reset_unix": data.get("next_character_count_reset_unix"),
        }
