from snarf.capabilities.audio_io import LocalAudioIO
from snarf.runtime.base import Channel
from snarf.voice.router import VoiceRouter


class VoiceChannel(Channel):
    name = "voice"

    def __init__(self):
        # Antes cableaba ElevenLabsSTT/ElevenLabsTTS directo — ahora pasa por
        # el mismo VoiceRouter que la interfaz web, así que cambiar de
        # proveedor (o mover el tier local a un VPS) también aplica acá sin
        # tocar este archivo.
        self._voice = VoiceRouter()
        self._audio = LocalAudioIO()

    @property
    def available(self) -> bool:
        return self._voice.stt_available and self._voice.tts_status()["available"]

    def receive(self) -> str:
        if not self.available:
            raise RuntimeError(
                "Canal de voz no disponible: revisar voice/config.yaml y las credenciales configuradas."
            )
        input("Presioná Enter para empezar a hablar...")
        self._audio.start_recording()
        input("Escuchando... presioná Enter de nuevo para terminar.")
        audio_bytes = self._audio.stop_recording()
        return self._voice.transcribe(audio_bytes)

    def send(self, message: str) -> None:
        if not self.available:
            raise RuntimeError(
                "Canal de voz no disponible: revisar voice/config.yaml y las credenciales configuradas."
            )
        audio_bytes = self._voice.speak(message)
        self._audio.play(audio_bytes)
