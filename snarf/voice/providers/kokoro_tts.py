import requests

from snarf.telemetry import usage_tracker
from snarf.voice.interface import TTSProvider

DEFAULT_BASE_URL = "http://localhost:8880"
# em_alex: voz masculina real de Kokoro-82M en español (lang_code 'e' — hay
# tres voces reales: ef_dora femenina, em_alex y em_santa masculinas).
# Elegida por continuidad con "Antonio" (voz actual de ElevenLabs, masculina)
# hasta escuchar las tres y confirmar con el fundador cuál prefiere de verdad
# — pendiente de verificación por oído, no una afirmación de calidad.
DEFAULT_VOICE = "em_alex"
MODEL_ID = "kokoro"


class KokoroTTS(TTSProvider):
    """Cliente HTTP contra el contenedor Docker de Kokoro-FastAPI (tier 'local').

    Deliberadamente NO embebe el modelo en el proceso de Snarf — corre siempre
    detrás de un endpoint HTTP compatible con la API de OpenAI
    (POST /v1/audio/speech). Mover este tier de la Mac a un VPS es cambiar
    `base_url` en voice/config.yaml, nunca tocar este código (ver Parte 4).
    """

    name = "kokoro_tts"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, voice: str = DEFAULT_VOICE):
        self._base_url = base_url.rstrip("/")
        self._voice = voice

    @property
    def available(self) -> bool:
        # No hay un /health documentado en Kokoro-FastAPI — /v1/audio/voices
        # es un endpoint real confirmado y no sintetiza nada, así que sirve
        # como probe barato de "el contenedor está arriba y responde".
        try:
            response = requests.get(f"{self._base_url}/v1/audio/voices", timeout=2)
            return response.ok
        except requests.RequestException:
            return False

    def speak(self, text: str, voice: str | None = None, audio_format: str = "mp3") -> bytes:
        response = requests.post(
            f"{self._base_url}/v1/audio/speech",
            json={
                "model": MODEL_ID,
                "input": text,
                "voice": voice or self._voice,
                "response_format": audio_format,
            },
            # 30s real, en producción, no alcanzó: un timeout real de "Read
            # timed out" en el log apunta a un cold-start del contenedor tras
            # estar inactivo (la síntesis en caliente tarda ~2-3s).
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"Kokoro TTS {response.status_code}: {response.text}")
        usage_tracker.record_kokoro_tts_call(len(text))
        return response.content
