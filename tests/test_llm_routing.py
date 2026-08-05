import anthropic
import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import OpenAICompatibleLLM
from snarf.runtime import llm_routing


def _anthropic_status_error(status_code: int, message: str = "error real de la API"):
    # Mismo tipo de excepción real que tira el SDK `anthropic` — no un mock:
    # is_provider_level_error hace isinstance contra la clase real.
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return anthropic.APIStatusError(message, response=response, body={"error": {"message": message}})


def test_load_routing_returns_the_default_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    assert llm_routing.load_routing() == llm_routing.DEFAULT_ROUTING


def test_save_and_load_routing_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    saved = llm_routing.save_routing({"orchestrator": {"provider": "gemini", "model": "gemini-3-pro-preview"}})
    assert saved["orchestrator"] == {"provider": "gemini", "model": "gemini-3-pro-preview"}
    # Los roles no incluidos en el PUT se quedan con su default, nunca desaparecen.
    assert saved["gmail_digest"] == llm_routing.DEFAULT_ROUTING["gmail_digest"]

    loaded = llm_routing.load_routing()
    assert loaded == saved


def test_save_routing_ignores_an_unknown_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    saved = llm_routing.save_routing({"orchestrator": {"provider": "un-proveedor-inventado", "model": "x"}})
    assert saved["orchestrator"] == llm_routing.DEFAULT_ROUTING["orchestrator"]


def test_save_routing_ignores_a_role_that_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    routing = llm_routing.save_routing({"rol_inventado": {"provider": "anthropic", "model": "x"}})
    assert "rol_inventado" not in routing
    assert set(routing.keys()) == set(llm_routing.ROLES)


def test_build_llm_defaults_to_the_local_fast_model_for_every_role_except_drive_vision(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    for role in llm_routing.ROLES:
        llm = llm_routing.build_llm(role)
        if role == "drive_vision":
            # drive_vision necesita soporte real de imágenes — Qwen3-4B local
            # es texto-solo, así que ese rol se queda en un proveedor con
            # visión real incluso en el default.
            assert isinstance(llm, AnthropicLLM)
        else:
            assert isinstance(llm, OpenAICompatibleLLM)
            assert llm.model == llm_routing.MLX_LOCAL_FAST_MODEL


def test_build_llm_resolves_gemini(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    llm_routing.save_routing({"orchestrator": {"provider": "gemini", "model": "gemini-3-pro-preview"}})
    llm = llm_routing.build_llm("orchestrator")
    assert isinstance(llm, GeminiLLM)
    assert llm.model == "gemini-3-pro-preview"


def test_build_llm_resolves_openai(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    llm_routing.save_routing({"orchestrator": {"provider": "openai", "model": "gpt-5"}})
    llm = llm_routing.build_llm("orchestrator")
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm.model == "gpt-5"
    assert llm._api_key_env == "OPENAI_API_KEY"


def test_build_llm_resolves_xai_via_the_openai_compatible_capability(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    llm_routing.save_routing({"orchestrator": {"provider": "xai", "model": "grok-4.1-fast"}})
    llm = llm_routing.build_llm("orchestrator")
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm._api_key_env == "XAI_API_KEY"


def test_build_llm_resolves_groq_llama_reusing_the_existing_groq_key(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    llm_routing.save_routing({"orchestrator": {"provider": "groq_llama", "model": "llama-4-scout"}})
    llm = llm_routing.build_llm("orchestrator")
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm._api_key_env == "GROQ_API_KEY"


def test_available_providers_reflects_real_env_vars(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # mlx_local/mlx_local_fast/mlx_local_mid no exigen ninguna credencial
    # (corren en esta Mac) — siempre cuentan como disponibles, incluso sin
    # ninguna env var cargada.
    assert set(llm_routing.available_providers()) == {"mlx_local", "mlx_local_fast", "mlx_local_mid"}

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert set(llm_routing.available_providers()) == {"gemini", "mlx_local", "mlx_local_fast", "mlx_local_mid"}


def test_mlx_local_is_always_available_without_any_credential(monkeypatch):
    for env_var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    assert "mlx_local" in llm_routing.available_providers()
    assert "mlx_local_fast" in llm_routing.available_providers()
    assert "mlx_local_mid" in llm_routing.available_providers()


def test_build_llm_resolves_mlx_local_without_a_real_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm_routing.save_routing({"orchestrator": {"provider": "mlx_local", "model": "mlx-community/algun-modelo"}})
    llm = llm_routing.build_llm("orchestrator")
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm._local is True
    assert llm.available is True


def test_build_llm_resolves_mlx_local_fast_without_a_real_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm_routing.save_routing(
        {"history_compaction": {"provider": "mlx_local_fast", "model": "mlx-community/Qwen3-4B-Instruct-2507-4bit"}}
    )
    llm = llm_routing.build_llm("history_compaction")
    assert isinstance(llm, OpenAICompatibleLLM)
    assert llm._local is True
    assert llm.available is True
    assert llm.model == "mlx-community/Qwen3-4B-Instruct-2507-4bit"


# --- is_provider_level_error (fallback automático, ADR de esta ronda) -----


def test_is_provider_level_error_true_for_the_real_anthropic_credit_error():
    # Caso real que disparó todo esto: Anthropic devuelve "credit balance is
    # too low" como un BadRequestError (400) — no hay un tipo dedicado.
    assert llm_routing.is_provider_level_error(_anthropic_status_error(400, "credit balance is too low")) is True


def test_is_provider_level_error_true_for_rate_limit():
    assert llm_routing.is_provider_level_error(_anthropic_status_error(429)) is True


def test_is_provider_level_error_true_for_auth_and_server_errors():
    for code in (401, 403, 500, 502, 503, 504, 529):
        assert llm_routing.is_provider_level_error(_anthropic_status_error(code)) is True


def test_is_provider_level_error_false_for_an_unmapped_status_code():
    # 422 (unprocessable entity) es casi siempre un bug real nuestro en la
    # forma del request, no algo que cambiar de proveedor arregle.
    assert llm_routing.is_provider_level_error(_anthropic_status_error(422)) is False


def test_is_provider_level_error_false_for_a_generic_exception():
    assert llm_routing.is_provider_level_error(ValueError("bug real nuestro, no del proveedor")) is False


def test_is_provider_level_error_true_for_a_real_gemini_client_error():
    exc = genai_errors.ClientError(429, {"error": {"message": "rate limited"}}, response=None)
    assert llm_routing.is_provider_level_error(exc) is True


def test_is_provider_level_error_true_for_a_connection_error():
    # Reabierto para la migración a mlx_local (ver ADR de esta ronda): un
    # proveedor LOCAL caído (mlx_lm.server sin correr) no devuelve ningún
    # status HTTP — devuelve un error de conexión real, porque no hay nada
    # escuchando en ese puerto.
    request = httpx.Request("POST", "http://localhost:8990/v1/chat/completions")
    assert llm_routing.is_provider_level_error(anthropic.APIConnectionError(request=request)) is True
    assert llm_routing.is_provider_level_error(openai.APIConnectionError(request=request)) is True


# --- attempt_fallback -------------------------------------------------


def test_attempt_fallback_does_nothing_for_a_non_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    entry = llm_routing.DEFAULT_ROUTING["dashboard_curator"]
    result = llm_routing.attempt_fallback("dashboard_curator", entry, ValueError("bug real nuestro"))
    assert result == (None, None)
    assert llm_routing.load_routing()["dashboard_curator"] == entry  # nada cambió


def test_attempt_fallback_switches_to_the_next_available_provider_and_leaves_a_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic", "xai"])

    class _Response:
        text = "respuesta real de xai"

    def fake_build(provider, model):
        assert provider == "xai"  # anthropic (el que falló) nunca debería reintentarse a sí mismo
        return type("F", (), {"generate": lambda self, **kw: _Response()})()

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    entry = {"provider": "anthropic", "model": "claude-haiku-4-5"}
    exc = _anthropic_status_error(400, "credit balance is too low")

    response, new_entry = llm_routing.attempt_fallback("dashboard_curator", entry, exc)

    assert response.text == "respuesta real de xai"
    assert new_entry == {"provider": "xai", "model": "grok-4-1-fast"}
    # se persiste como nuevo default real del rol
    assert llm_routing.load_routing()["dashboard_curator"] == new_entry
    # y queda un registro trazable real
    events = llm_routing.recent_fallback_events()
    assert len(events) == 1
    assert events[0]["role"] == "dashboard_curator"
    assert events[0]["from"] == entry
    assert events[0]["to"] == new_entry
    assert "credit balance is too low" in events[0]["error"]
    assert isinstance(events[0]["timestamp"], float)


def test_attempt_fallback_returns_none_when_every_provider_fails_and_leaves_no_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic", "xai", "gemini"])

    def fake_build(provider, model):
        def boom(self, **kw):
            raise RuntimeError(f"{provider} también falló")

        return type("F", (), {"generate": boom})()

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    entry = {"provider": "anthropic", "model": "claude-haiku-4-5"}
    result = llm_routing.attempt_fallback("dashboard_curator", entry, _anthropic_status_error(500))

    assert result == (None, None)
    assert llm_routing.load_routing()["dashboard_curator"] == llm_routing.DEFAULT_ROUTING["dashboard_curator"]
    assert llm_routing.recent_fallback_events() == []


def test_attempt_fallback_never_tries_a_provider_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic"])  # xai NO tiene credencial

    def fake_build(provider, model):
        raise AssertionError("no debería construirse nada — no hay otro proveedor disponible")

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    entry = {"provider": "anthropic", "model": "claude-haiku-4-5"}
    result = llm_routing.attempt_fallback("dashboard_curator", entry, _anthropic_status_error(500))
    assert result == (None, None)


def test_attempt_fallback_uses_the_conservative_vision_order_for_drive_vision(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic", "xai", "gemini"])
    tried = []

    def fake_build(provider, model):
        tried.append(provider)

        def gen(self, **kw):
            if provider != "gemini":
                raise RuntimeError("no soporta visión real")
            return type("R", (), {"text": "descripción real de la imagen"})()

        return type("F", (), {"generate": gen})()

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    entry = {"provider": "anthropic", "model": "claude-haiku-4-5"}
    response, new_entry = llm_routing.attempt_fallback("drive_vision", entry, _anthropic_status_error(500))

    assert new_entry["provider"] == "gemini"
    assert "xai" not in tried  # drive_vision nunca prueba proveedores sin soporte confirmado de visión


# --- recent_fallback_events ---------------------------------------------


def test_recent_fallback_events_empty_without_a_log_file(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "no_existe.jsonl")
    assert llm_routing.recent_fallback_events() == []


def test_recent_fallback_events_filters_by_since(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "log.jsonl")
    llm_routing._append_fallback_log({"timestamp": 100.0, "role": "x", "from": {}, "to": {}, "error": "e"})
    llm_routing._append_fallback_log({"timestamp": 200.0, "role": "y", "from": {}, "to": {}, "error": "e"})
    events = llm_routing.recent_fallback_events(since=150.0)
    assert [e["role"] for e in events] == ["y"]


# --- build_resilient_llm / _ResilientLLM ---------------------------------


def test_build_resilient_llm_behaves_normally_when_the_provider_works(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(
        llm_routing, "_build", lambda provider, model: type("F", (), {"available": True, "generate": lambda self, **kw: type("R", (), {"text": "todo bien"})()})()
    )
    llm = llm_routing.build_resilient_llm("dashboard_curator")
    assert llm.available is True
    assert llm.generate(system="x", messages=[]).text == "todo bien"


def test_build_resilient_llm_falls_back_and_self_heals_for_the_next_call(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic", "xai"])
    # Fija el proveedor inicial a mano en vez de confiar en DEFAULT_ROUTING
    # (que hoy es mlx_local_fast) — este test verifica el fallback ante un
    # error real de proveedor, no cuál es el default vigente.
    llm_routing.save_routing({"dashboard_curator": {"provider": "anthropic", "model": "claude-haiku-4-5"}})
    calls = []

    def fake_build(provider, model):
        calls.append(provider)

        def gen(self, **kw):
            if provider == "anthropic":
                raise _anthropic_status_error(400, "credit balance is too low")
            return type("R", (), {"text": f"respuesta de {provider}"})()

        return type("F", (), {"generate": gen})()

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    llm = llm_routing.build_resilient_llm("dashboard_curator")

    result = llm.generate(system="x", messages=[])
    assert result.text == "respuesta de xai"

    # Segunda llamada al MISMO objeto: usa directo la instancia de xai ya
    # cacheada (self._llm) — ni siquiera vuelve a pasar por _build, nunca
    # vuelve a intentar (ni fallar contra) anthropic. El objeto se auto-cura.
    calls.clear()
    result2 = llm.generate(system="x", messages=[])
    assert result2.text == "respuesta de xai"
    assert calls == []


def test_build_resilient_llm_raises_the_original_exception_when_every_provider_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    monkeypatch.setattr(llm_routing, "available_providers", lambda: ["anthropic"])  # sin otro candidato real

    def fake_build(provider, model):
        def boom(self, **kw):
            raise _anthropic_status_error(500, "el proveedor está caído de verdad")

        return type("F", (), {"generate": boom})()

    monkeypatch.setattr(llm_routing, "_build", fake_build)
    llm = llm_routing.build_resilient_llm("dashboard_curator")
    with pytest.raises(anthropic.APIStatusError, match="caído de verdad"):
        llm.generate(system="x", messages=[])
