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
    # Bug real encontrado al cargar credenciales reales en .env para el LLM
    # multi-proveedor: a diferencia de ANTHROPIC_API_KEY de arriba, estas no
    # se borraban acá — build_llm() las lee directo de os.environ, así que
    # cualquier test que construyera una Capacidad con el routing default (o
    # cualquier rol ruteado a estos proveedores) hubiera podido disparar una
    # llamada real. GROQ_API_KEY se suma también por el mismo motivo, ahora
    # que además de STT se usa para el rol groq_llama del LLM.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
