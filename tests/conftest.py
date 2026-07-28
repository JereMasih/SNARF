import pytest


@pytest.fixture(autouse=True)
def _no_real_credentials(monkeypatch):
    """Ningún test debe depender de, ni disparar, llamadas de red reales a
    Anthropic, ElevenLabs, Google o Voyage. Se limpian las variables de
    entorno relevantes antes de cada test, sin importar qué haya en el .env
    real."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
