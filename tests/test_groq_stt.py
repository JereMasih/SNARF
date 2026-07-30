from types import SimpleNamespace

from snarf.voice.providers.groq_stt import GroqSTT


def make_stt():
    stt = GroqSTT.__new__(GroqSTT)
    stt._api_key = "fake"
    return stt


def fake_post(payload, monkeypatch, module):
    response = SimpleNamespace(ok=True, json=lambda: payload)
    monkeypatch.setattr(module.requests, "post", lambda *a, **k: response)


def test_transcribe_records_the_real_audio_duration_from_verbose_json(monkeypatch):
    from snarf.voice.providers import groq_stt as module

    fake_post({"text": "hola mundo", "duration": 3.4}, monkeypatch, module)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_groq_stt_call", lambda duration, **k: recorded.append(duration))

    text = make_stt().transcribe(b"audio-bytes")

    assert text == "hola mundo"
    assert recorded == [3.4]


def test_transcribe_raises_a_clear_error_on_http_failure(monkeypatch):
    from snarf.voice.providers import groq_stt as module

    response = SimpleNamespace(ok=False, status_code=401, text="invalid api key")
    monkeypatch.setattr(module.requests, "post", lambda *a, **k: response)

    try:
        make_stt().transcribe(b"audio-bytes")
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as exc:
        assert "401" in str(exc)


def test_available_is_false_without_an_api_key():
    stt = GroqSTT.__new__(GroqSTT)
    stt._api_key = None
    assert stt.available is False
