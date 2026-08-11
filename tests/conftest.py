import pytest

from snarf.telemetry import dispatcher, event_buffer, n8n_webhook_sink, redis_sink


@pytest.fixture(autouse=True)
def _reset_telemetry_dispatcher():
    """El dispatcher de telemetría (Fase 1 del plan de observabilidad,
    snarf/telemetry/dispatcher.py) y sus subscribers opcionales (Fase 2:
    event_buffer.py/redis_sink.py; Fase 4: n8n_webhook_sink.py) son estado a
    nivel de módulo — sin este fixture, un subscriber o un contador de un
    test seguiría vivo para el siguiente. Se limpia antes Y después: antes,
    por si un test anterior dejó algo sin limpiar; después, se espera a que
    la cola async termine de entregar (drain) antes de resetear, para no
    dejar callbacks colgando a mitad de ejecución."""
    dispatcher.reset()
    event_buffer.reset()
    redis_sink.reset()
    n8n_webhook_sink.reset()
    yield
    dispatcher.drain(timeout=1.0)
    dispatcher.reset()
    event_buffer.reset()
    redis_sink.reset()
    n8n_webhook_sink.reset()


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
    # SNARF_REDIS_URL (Fase 2 del plan de observabilidad, snarf/telemetry/
    # redis_sink.py): sin esto, un .env real con Redis configurado haría que
    # cada test instale de verdad un subscriber que intenta hablarle a un
    # Redis real — mismo criterio de hermeticidad que el resto de este
    # fixture.
    monkeypatch.delenv("SNARF_REDIS_URL", raising=False)
    # N8N_WEBHOOK_URL (Fase 4, snarf/telemetry/n8n_webhook_sink.py) y
    # N8N_CONTROL_TOKEN (app.py, ruta GET /n8n/status) — mismo criterio de
    # hermeticidad que SNARF_REDIS_URL arriba.
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("N8N_CONTROL_TOKEN", raising=False)
