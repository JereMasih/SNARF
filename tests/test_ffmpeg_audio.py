from types import SimpleNamespace

from snarf.capabilities.ffmpeg_audio import FfmpegAudioExtractor


def test_available_reflects_whether_ffmpeg_binary_is_on_path(monkeypatch):
    from snarf.capabilities import ffmpeg_audio as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert FfmpegAudioExtractor().available is True

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert FfmpegAudioExtractor().available is False


def test_extract_audio_raises_clearly_when_ffmpeg_is_not_installed(monkeypatch):
    from snarf.capabilities import ffmpeg_audio as module

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    try:
        FfmpegAudioExtractor().extract_audio(b"video-bytes")
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as exc:
        assert "ffmpeg" in str(exc).lower()


def test_extract_audio_raises_with_ffmpeg_stderr_when_it_fails(monkeypatch):
    from snarf.capabilities import ffmpeg_audio as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    fake_result = SimpleNamespace(returncode=1, stderr=b"formato no reconocido")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: fake_result)

    try:
        FfmpegAudioExtractor().extract_audio(b"video-bytes-invalidos")
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as exc:
        assert "formato no reconocido" in str(exc)


def test_extract_audio_returns_the_extracted_bytes_on_success(monkeypatch):
    from snarf.capabilities import ffmpeg_audio as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def fake_run(cmd, capture_output=True):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"fake-mp3-bytes")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    audio = FfmpegAudioExtractor().extract_audio(b"video-bytes")
    assert audio == b"fake-mp3-bytes"
