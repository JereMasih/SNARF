from snarf.capabilities.audio_io import LocalAudioIO
from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT
from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS
from snarf.runtime.base import Channel


class VoiceChannel(Channel):
    name = "voice"

    def __init__(self):
        self._stt = ElevenLabsSTT()
        self._tts = ElevenLabsTTS()
        self._audio = LocalAudioIO()

    @property
    def available(self) -> bool:
        return self._stt.available and self._tts.available

    def receive(self) -> str:
        if not self.available:
            raise RuntimeError(
                "Canal de voz no disponible: falta ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID."
            )
        input("Presioná Enter para empezar a hablar...")
        self._audio.start_recording()
        input("Escuchando... presioná Enter de nuevo para terminar.")
        audio_bytes = self._audio.stop_recording()
        return self._stt.transcribe(audio_bytes)

    def send(self, message: str) -> None:
        if not self.available:
            raise RuntimeError(
                "Canal de voz no disponible: falta ELEVENLABS_API_KEY o ELEVENLABS_VOICE_ID."
            )
        audio_bytes = self._tts.synthesize(message)
        self._audio.play(audio_bytes)
