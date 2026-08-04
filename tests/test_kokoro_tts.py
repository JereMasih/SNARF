from types import SimpleNamespace

from snarf.voice.providers.kokoro_tts import KokoroTTS


def make_tts():
    return KokoroTTS.__new__(KokoroTTS).__class__(base_url="http://localhost:8880", voice="em_alex")


def test_speak_records_character_count_and_uses_the_configured_voice_by_default(monkeypatch):
    from snarf.voice.providers import kokoro_tts as module

    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return SimpleNamespace(ok=True, content=b"audio-bytes")

    monkeypatch.setattr(module.requests, "post", fake_post)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_kokoro_tts_call", lambda chars, **k: recorded.append(chars))

    audio = make_tts().speak("hola mundo")

    assert audio == b"audio-bytes"
    assert recorded == [len("hola mundo")]
    assert captured["url"] == "http://localhost:8880/v1/audio/speech"
    assert captured["json"]["voice"] == "em_alex"
    assert captured["json"]["model"] == "kokoro"


def test_speak_lets_the_caller_override_the_default_voice(monkeypatch):
    from snarf.voice.providers import kokoro_tts as module

    captured = {}
    monkeypatch.setattr(
        module.requests, "post", lambda url, json, timeout: captured.update(json=json) or SimpleNamespace(ok=True, content=b"x")
    )
    # Sin mockear esto, .speak() de verdad escribía en data/usage_log.jsonl real
    # (costo $0.0, pero igual una entrada sintética de menos que limpiar).
    monkeypatch.setattr(module.usage_tracker, "record_kokoro_tts_call", lambda chars, **k: None)

    make_tts().speak("hola", voice="ef_dora")
    assert captured["json"]["voice"] == "ef_dora"


def test_speak_raises_a_clear_error_on_http_failure(monkeypatch):
    from snarf.voice.providers import kokoro_tts as module

    monkeypatch.setattr(
        module.requests, "post", lambda *a, **k: SimpleNamespace(ok=False, status_code=500, text="internal error")
    )
    try:
        make_tts().speak("hola")
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as exc:
        assert "500" in str(exc)


def test_available_is_false_when_the_container_is_unreachable(monkeypatch):
    from snarf.voice.providers import kokoro_tts as module

    def boom(*a, **k):
        raise module.requests.RequestException("connection refused")

    monkeypatch.setattr(module.requests, "get", boom)
    assert make_tts().available is False


def test_available_is_true_when_the_container_responds_ok(monkeypatch):
    from snarf.voice.providers import kokoro_tts as module

    monkeypatch.setattr(module.requests, "get", lambda *a, **k: SimpleNamespace(ok=True))
    assert make_tts().available is True
