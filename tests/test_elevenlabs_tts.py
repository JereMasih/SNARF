from types import SimpleNamespace

from snarf.capabilities.elevenlabs_tts import ElevenLabsTTS


def make_tts():
    tts = ElevenLabsTTS.__new__(ElevenLabsTTS)
    tts._api_key = "fake"
    tts._voice_id = "fake-voice"
    return tts


def test_synthesize_records_character_count(monkeypatch):
    from snarf.capabilities import elevenlabs_tts as module

    response = SimpleNamespace(raise_for_status=lambda: None, content=b"audio-bytes")
    monkeypatch.setattr(module.requests, "post", lambda *a, **k: response)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_elevenlabs_tts_call", lambda chars, **k: recorded.append(chars))

    audio = make_tts().synthesize("hola mundo")

    assert audio == b"audio-bytes"
    assert recorded == [len("hola mundo")]
