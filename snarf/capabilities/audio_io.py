import io
import subprocess
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf

from snarf.capabilities.base import Capability


class LocalAudioIO(Capability):
    name = "local_audio_io"

    def __init__(self):
        self._stream = None
        self._frames = []
        self._samplerate = 16000

    @property
    def available(self) -> bool:
        return True

    def play(self, audio_bytes: bytes) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            path = f.name
        subprocess.run(["afplay", path], check=True)

    def record(self, seconds: float = 5.0, samplerate: int = 16000) -> bytes:
        audio = sd.rec(
            int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16"
        )
        sd.wait()
        return self._to_wav_bytes(audio, samplerate)

    def start_recording(self, samplerate: int = 16000) -> None:
        self._frames = []
        self._samplerate = samplerate

        def callback(indata, frames, time_info, status):
            self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=samplerate, channels=1, dtype="int16", callback=callback
        )
        self._stream.start()

    def stop_recording(self) -> bytes:
        if self._stream is None:
            raise RuntimeError("No hay una grabación en curso.")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if self._frames:
            audio = np.concatenate(self._frames, axis=0)
        else:
            audio = np.zeros((0, 1), dtype="int16")
        return self._to_wav_bytes(audio, self._samplerate)

    @staticmethod
    def _to_wav_bytes(audio: np.ndarray, samplerate: int) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, audio, samplerate, format="WAV")
        return buffer.getvalue()
