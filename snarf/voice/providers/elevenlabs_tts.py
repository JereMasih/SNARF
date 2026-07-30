from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS as _ElevenLabsTTSCapability
from snarf.voice.interface import TTSProvider


class ElevenLabsTTSProvider(TTSProvider):
    """Adaptador de la Capacidad ElevenLabsTTS existente al contrato TTSProvider.

    Tier 'premium' únicamente (ver ADR de la capa de voz): el router nunca
    escala acá por su cuenta — solo cuando el fundador lo pide explícito o la
    tarea produce un asset publicable. Reusa la Capacidad ya existente (no la
    reimplementa) para no duplicar el registro de uso que ya hace
    ElevenLabsTTS.synthesize() ni la lógica de subscription_info() del
    dashboard, que sigue viviendo en snarf.capabilities.elevenlabs_tts.
    """

    name = "elevenlabs_tts_premium"

    def __init__(self):
        self._capability = _ElevenLabsTTSCapability()

    @property
    def available(self) -> bool:
        return self._capability.available

    def speak(self, text: str, voice: str | None = None, audio_format: str = "mp3") -> bytes:
        return self._capability.synthesize(text)
