import hashlib
import time
import uuid
from pathlib import Path

DEFAULT_AUDIO_DIR = Path("data/audio")

# Nombres generados acá siempre son uuid4().hex + extensión, o el prefijo
# fijo "tts_" + hash — nunca contienen "/" ni "..", pero path_for() igual
# valida contra eso antes de tocar disco: es el único punto de la app que
# arma una ruta de archivo a partir de un valor que llega crudo por URL.
_VALID_EXTS = {"webm", "mp4", "ogg", "mp3", "wav"}

MIME_BY_EXT = {
    "webm": "audio/webm",
    "mp4": "audio/mp4",
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}


class AudioStore:
    """Guarda notas de voz del usuario y respuestas de voz de Snarf ya
    sintetizadas, ambas como archivos reales en disco (no en el log de
    episodic_memory.jsonl, que es texto puro) — un id apunta a un archivo,
    nunca al contenido en sí. Las transcripciones/respuestas de texto viven
    donde siempre vivieron (EpisodicMemory, para siempre); estos archivos
    son la parte "cara" en espacio que sí conviene purgar con el tiempo."""

    def __init__(self, directory: Path = DEFAULT_AUDIO_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, ext: str) -> str:
        ext = ext.lower().lstrip(".")
        if ext not in _VALID_EXTS:
            ext = "webm"
        audio_id = f"{uuid.uuid4().hex}.{ext}"
        (self.directory / audio_id).write_bytes(data)
        return audio_id

    def path_for(self, audio_id: str) -> Path | None:
        if not audio_id or "/" in audio_id or "\\" in audio_id or ".." in audio_id:
            return None
        ext = audio_id.rsplit(".", 1)[-1].lower() if "." in audio_id else ""
        if ext not in _VALID_EXTS:
            return None
        path = self.directory / audio_id
        return path if path.is_file() else None

    # --- caché de TTS por contenido: mismo texto -> mismo archivo, nunca se
    # vuelve a pagar una síntesis real de ElevenLabs por una respuesta ya
    # sintetizada antes (el fundador lo pidió explícitamente: "posibilidad
    # de escuchar varias veces cada audio" sin repetir el costo/la demora). ---
    def _tts_cache_id(self, text: str) -> str:
        return "tts_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:32] + ".mp3"

    def get_cached_tts(self, text: str) -> bytes | None:
        path = self.directory / self._tts_cache_id(text)
        return path.read_bytes() if path.is_file() else None

    def save_tts(self, text: str, data: bytes) -> str:
        audio_id = self._tts_cache_id(text)
        (self.directory / audio_id).write_bytes(data)
        return audio_id

    def purge_older_than(self, max_age_seconds: float) -> int:
        cutoff = time.time() - max_age_seconds
        deleted = 0
        for f in self.directory.glob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        return deleted
