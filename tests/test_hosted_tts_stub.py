import pytest

from snarf.voice.providers.hosted_tts import HostedTTSNotConfigured


def test_hosted_tts_stub_is_never_available():
    assert HostedTTSNotConfigured().available is False


def test_hosted_tts_stub_raises_a_clear_error_if_ever_called():
    with pytest.raises(RuntimeError, match="hosted"):
        HostedTTSNotConfigured().speak("hola")
