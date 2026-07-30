from snarf.voice.providers.elevenlabs_tts import ElevenLabsTTSProvider


def test_speak_delegates_to_the_underlying_capability(monkeypatch):
    provider = ElevenLabsTTSProvider()
    monkeypatch.setattr(provider._capability, "synthesize", lambda text: b"audio for " + text.encode())

    assert provider.speak("hola") == b"audio for hola"


def test_available_reflects_the_underlying_capability(monkeypatch):
    provider = ElevenLabsTTSProvider()
    monkeypatch.setattr(provider._capability, "_api_key", None)
    assert provider.available is False

    monkeypatch.setattr(provider._capability, "_api_key", "fake-key")
    monkeypatch.setattr(provider._capability, "_voice_id", "fake-voice")
    assert provider.available is True
