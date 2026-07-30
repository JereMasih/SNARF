import pytest

from snarf.voice.router import TierUnavailable, VoiceRouter


class FakeSTT:
    def __init__(self, available=True, text="transcripto", raises=None):
        self._available = available
        self._text = text
        self._raises = raises

    @property
    def available(self):
        return self._available

    def transcribe(self, audio_bytes, filename="audio.webm"):
        if self._raises:
            raise self._raises
        return self._text


class FakeTTS:
    def __init__(self, available=True, audio=b"audio"):
        self._available = available
        self._audio = audio
        self.calls = []

    @property
    def available(self):
        return self._available

    def speak(self, text, voice=None, audio_format="mp3"):
        self.calls.append(text)
        return self._audio


def make_router(tmp_path, monkeypatch, stt_providers, tts_providers):
    import snarf.voice.router as router_module

    monkeypatch.setattr(router_module, "STT_PROVIDERS", stt_providers)
    monkeypatch.setattr(router_module, "TTS_PROVIDERS", tts_providers)
    monkeypatch.setattr(router_module, "PROVIDER_CONFIG_SECTION", {})

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "stt:\n  primary: primary_stt\n  fallback: fallback_stt\n"
        "tts:\n  tiers:\n    local: local_tts\n    hosted: hosted_tts\n    premium: premium_tts\n",
        encoding="utf-8",
    )
    return router_module.VoiceRouter(config_path=config_path)


def test_transcribe_uses_the_primary_provider_when_available(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": lambda: FakeSTT(text="del primario"), "fallback_stt": lambda: FakeSTT(text="del fallback")},
        {"local_tts": FakeTTS, "hosted_tts": FakeTTS, "premium_tts": FakeTTS},
    )
    assert router.transcribe(b"x") == "del primario"


def test_transcribe_falls_back_when_primary_is_unavailable(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": lambda: FakeSTT(available=False), "fallback_stt": lambda: FakeSTT(text="del fallback")},
        {"local_tts": FakeTTS, "hosted_tts": FakeTTS, "premium_tts": FakeTTS},
    )
    assert router.transcribe(b"x") == "del fallback"


def test_transcribe_falls_back_when_the_primary_provider_raises(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {
            "primary_stt": lambda: FakeSTT(raises=RuntimeError("Groq caído")),
            "fallback_stt": lambda: FakeSTT(text="del fallback"),
        },
        {"local_tts": FakeTTS, "hosted_tts": FakeTTS, "premium_tts": FakeTTS},
    )
    assert router.transcribe(b"x") == "del fallback"


def test_transcribe_raises_when_neither_stt_provider_is_available(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": lambda: FakeSTT(available=False), "fallback_stt": lambda: FakeSTT(available=False)},
        {"local_tts": FakeTTS, "hosted_tts": FakeTTS, "premium_tts": FakeTTS},
    )
    with pytest.raises(RuntimeError):
        router.transcribe(b"x")


def test_speak_without_a_tier_only_tries_local_and_never_escalates_to_premium_in_silence(tmp_path, monkeypatch):
    """Regla dura del diseño: si el tier local está caído, nunca se escala
    solo a 'premium'/'hosted' — eso requiere pedirlo explícito."""
    premium = FakeTTS(available=True)
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": FakeSTT, "fallback_stt": FakeSTT},
        {"local_tts": lambda: FakeTTS(available=False), "hosted_tts": lambda: FakeTTS(available=False), "premium_tts": lambda: premium},
    )
    with pytest.raises(TierUnavailable):
        router.speak("hola")
    assert premium.calls == []


def test_speak_uses_the_local_tier_by_default_when_it_is_available(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": FakeSTT, "fallback_stt": FakeSTT},
        {"local_tts": lambda: FakeTTS(audio=b"local-audio"), "hosted_tts": FakeTTS, "premium_tts": FakeTTS},
    )
    assert router.speak("hola") == b"local-audio"


def test_speak_with_an_explicit_tier_uses_exactly_that_tier(tmp_path, monkeypatch):
    premium = FakeTTS(audio=b"premium-audio")
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": FakeSTT, "fallback_stt": FakeSTT},
        {"local_tts": lambda: FakeTTS(available=False), "hosted_tts": FakeTTS, "premium_tts": lambda: premium},
    )
    assert router.speak("hola", tier="premium") == b"premium-audio"
    assert premium.calls == ["hola"]


def test_tts_status_reports_which_tier_would_actually_respond(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": FakeSTT, "fallback_stt": FakeSTT},
        {
            "local_tts": lambda: FakeTTS(available=False),
            "hosted_tts": lambda: FakeTTS(available=False),
            "premium_tts": lambda: FakeTTS(available=True),
        },
    )
    assert router.tts_status() == {"available": True, "active_tier": "premium"}


def test_tts_status_reports_unavailable_when_no_tier_responds(tmp_path, monkeypatch):
    router = make_router(
        tmp_path,
        monkeypatch,
        {"primary_stt": FakeSTT, "fallback_stt": FakeSTT},
        {
            "local_tts": lambda: FakeTTS(available=False),
            "hosted_tts": lambda: FakeTTS(available=False),
            "premium_tts": lambda: FakeTTS(available=False),
        },
    )
    assert router.tts_status() == {"available": False, "active_tier": None}
