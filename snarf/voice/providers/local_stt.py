import io
import os

from snarf.telemetry import usage_tracker
from snarf.voice.interface import STTProvider

DEFAULT_MODEL_SIZE = os.environ.get("LOCAL_STT_MODEL_SIZE", "small")


class LocalWhisperSTT(STTProvider):
    """Fallback 100% local (faster-whisper, CPU) para cuando no hay red o Groq falla.

    Costo marginal cero, pero más lento y con más carga de CPU que Groq — por
    eso es fallback, nunca el default. A diferencia del tier local de TTS
    (Kokoro, que corre en cada turno de una conversación normal y por eso vive
    aislado en su propio contenedor Docker con endpoint HTTP — ver Parte 4),
    este solo se invoca cuando ya no hay red: en ese momento, un contenedor en
    la misma máquina no ofrece ningún aislamiento real que un proceso Python
    en memoria no ofrezca también, así que se mantiene simple (librería
    embebida, no un segundo servicio HTTP que mantener).
    """

    name = "local_whisper_stt"

    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE):
        self._model_size = model_size
        self._model = None

    @property
    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        if not self.available:
            raise RuntimeError(
                "faster-whisper no está instalado (fallback local de STT). "
                "Instalar con: pip install faster-whisper"
            )
        model = self._load_model()
        segments, info = model.transcribe(io.BytesIO(audio_bytes), language="es")
        text = " ".join(segment.text.strip() for segment in segments).strip()
        usage_tracker.record_local_stt_call(info.duration)
        return text
