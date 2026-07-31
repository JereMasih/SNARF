from snarf.capabilities.anthropic_llm import AnthropicLLM
from snarf.capabilities.gemini_llm import GeminiLLM
from snarf.capabilities.openai_compatible_llm import OpenAICompatibleLLM
from snarf.runtime import llm_routing


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


def test_build_llm_defaults_to_anthropic_for_every_role(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    for role in llm_routing.ROLES:
        assert isinstance(llm_routing.build_llm(role), AnthropicLLM)


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
    assert llm_routing.available_providers() == []

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert llm_routing.available_providers() == ["gemini"]
