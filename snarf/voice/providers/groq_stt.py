import os

import requests

from snarf.telemetry import detail, usage_tracker
from snarf.voice.interface import STTProvider

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"

# Groq factura con un piso efectivo de ~10s por request (ver
# snarf/telemetry/pricing.py, GROQ_STT_MIN_BILLED_SECONDS) — deliberadamente
# NO se agrupan clips cortos en una sola request para ahorrar ese piso. En el
# uso real de Snarf cada nota de voz ya llega como un único archivo completo
# (nunca fragmentos en streaming, ver /transcribe en app.py), así que el piso
# de 10s ya se paga una sola vez por nota, sea de 3s o de 30s — a volumen
# razonable (decenas de mensajes/día) representa fracciones de centavo. Armar
# una cola de agrupado de clips para ahorrar eso es la clase de complejidad
# que este mismo diseño pide evitar ("empezar barato, escalar solo ante
# evidencia de fallo real, nunca por anticipación"). Se documenta la decisión
# de no construirlo, no se omite en silencio.


class GroqSTT(STTProvider):
    """STT primario: Groq (whisper-large-v3-turbo), ~USD 0.04/hora de audio."""

    name = "groq_stt"

    def __init__(self):
        self._api_key = os.environ.get("GROQ_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        if not self.available:
            raise RuntimeError("GROQ_API_KEY no configurada (ver .env.example).")
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            data={"model": MODEL, "language": "es", "response_format": "verbose_json"},
            files={"file": (filename, audio_bytes)},
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(f"Groq STT {response.status_code}: {response.text}")
        payload = response.json()
        # verbose_json devuelve 'duration' real (segundos de audio), no el
        # tiempo de la request — es lo que Groq factura, no latencia de red.
        usage_tracker.record_groq_stt_call(payload.get("duration"), detalle=detail.truncate_detalle(payload.get("text")))
        return payload["text"]
