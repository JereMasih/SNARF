from types import SimpleNamespace

from snarf.capabilities.elevenlabs_stt import ElevenLabsSTT


def make_stt():
    stt = ElevenLabsSTT.__new__(ElevenLabsSTT)
    stt._api_key = "fake"
    return stt


def fake_post(payload, monkeypatch, module):
    response = SimpleNamespace(ok=True, json=lambda: payload)
    monkeypatch.setattr(module.requests, "post", lambda *a, **k: response)


def test_transcribe_records_duration_from_last_word_timestamp(monkeypatch):
    from snarf.capabilities import elevenlabs_stt as module

    fake_post({"text": "hola mundo", "words": [{"text": "hola", "end": 0.4}, {"text": "mundo", "end": 1.2}]}, monkeypatch, module)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_elevenlabs_stt_call", lambda duration, **k: recorded.append(duration))

    text = make_stt().transcribe(b"audio-bytes")

    assert text == "hola mundo"
    assert recorded == [1.2]


def test_transcribe_records_no_duration_when_words_are_missing(monkeypatch):
    from snarf.capabilities import elevenlabs_stt as module

    fake_post({"text": "hola"}, monkeypatch, module)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_elevenlabs_stt_call", lambda duration, **k: recorded.append(duration))

    make_stt().transcribe(b"audio-bytes")

    assert recorded == [None]
