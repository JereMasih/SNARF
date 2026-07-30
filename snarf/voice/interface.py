from abc import abstractmethod

from snarf.capabilities.base import Capability

# Contratos de la capa de voz — ningún proveedor real (Groq, Kokoro,
# ElevenLabs, lo que sea) se importa directamente desde el resto de Snarf.
# Todo pasa por STTProvider/TTSProvider, y el proveedor activo se elige en
# voice/config.yaml, nunca en código (ver ADR de la capa de voz).


class STTProvider(Capability):
    """Contrato para un proveedor de speech-to-text (lo que el fundador le habla a Snarf)."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        ...


class TTSProvider(Capability):
    """Contrato para un proveedor de text-to-speech (lo que Snarf le habla al fundador)."""

    @abstractmethod
    def speak(self, text: str, voice: str | None = None, audio_format: str = "mp3") -> bytes:
        ...
