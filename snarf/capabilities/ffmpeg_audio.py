import shutil
import subprocess
import tempfile
from pathlib import Path

from snarf.capabilities.base import Capability

FFMPEG_BINARY = "ffmpeg"


class FfmpegAudioExtractor(Capability):
    name = "ffmpeg_audio_extractor"

    @property
    def available(self) -> bool:
        return shutil.which(FFMPEG_BINARY) is not None

    def extract_audio(self, video_bytes: bytes, suffix: str = ".mp4") -> bytes:
        if not self.available:
            raise RuntimeError(f"'{FFMPEG_BINARY}' no está instalado en el sistema (ver .env.example).")
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / f"input{suffix}"
            audio_path = Path(tmpdir) / "output.mp3"
            video_path.write_bytes(video_bytes)
            result = subprocess.run(
                [FFMPEG_BINARY, "-i", str(video_path), "-vn", "-acodec", "libmp3lame", "-y", str(audio_path)],
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg falló extrayendo audio: {result.stderr.decode(errors='ignore')[:500]}")
            return audio_path.read_bytes()
