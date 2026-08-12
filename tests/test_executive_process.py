import snarf.executive.process as process
from snarf.executive.roles import CTO_CONFIG
from snarf.runtime import prompt_registry


class _FakeUnavailableLLM:
    available = False


class _FakeLLM:
    """Simula AnthropicLLM.generate(): llama a tool_handler una vez (como lo
    haría un modelo real pidiendo una herramienta) y devuelve una respuesta
    ya formada en el formato fijo de un rol ejecutivo."""

    available = True

    def __init__(self, tool_to_call: str | None = None):
        self._tool_to_call = tool_to_call
        self.received_tools = None
        self.received_system = None

    def generate(self, system, messages, tools=None, tool_handler=None):
        self.received_tools = tools
        self.received_system = system
        if self._tool_to_call and tool_handler:
            tool_handler(self._tool_to_call, {"query": "x"})
        return type(
            "R",
            (),
            {
                "text": (
                    "HEADLINE: postura real\n---\n"
                    f"CLAIM: dato real | BASIS: hecho | FUENTE: {self._tool_to_call or ''}\n"
                )
            },
        )()


class _FakeBridge:
    """Reemplaza _MCPToolBridge — nunca levanta un subproceso real en el
    test unitario (eso se verifica aparte, en vivo, ver ADR 0098)."""

    instances: list["_FakeBridge"] = []

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self.closed = False
        _FakeBridge.instances.append(self)

    def start(self, tool_subset):
        return [{"name": name, "description": "", "input_schema": {}} for name in sorted(tool_subset)]

    def call_tool(self, name, arguments):
        return {"echo": name, "arguments": arguments}

    def close(self):
        self.closed = True


def test_consult_role_degrades_honestly_when_llm_unavailable():
    result = process.consult_role(CTO_CONFIG, "¿conviene esto?", _FakeUnavailableLLM())
    assert result["opinions"] == []
    assert "cto" in result["headline"]


def test_consult_role_uses_the_bridge_and_parses_the_response(monkeypatch):
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    llm = _FakeLLM(tool_to_call="codebase_search")

    result = process.consult_role(CTO_CONFIG, "¿el código aguanta?", llm)

    assert result["headline"] == "postura real"
    assert result["opinions"] == [{"claim": "dato real", "basis": "hecho", "source": "codebase_search"}]
    # tools reales pasados al LLM vinieron del bridge, restringidos al
    # subset real del rol — nunca la lista completa del allowlist.
    assert {t["name"] for t in llm.received_tools} == set(CTO_CONFIG.mcp_tool_subset)


def test_consult_role_always_closes_the_bridge_even_on_llm_failure(monkeypatch):
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)

    class _BrokenLLM:
        available = True

        def generate(self, **kwargs):
            raise RuntimeError("boom")

    result = process.consult_role(CTO_CONFIG, "pregunta", _BrokenLLM())

    assert "boom" in result["headline"]
    assert _FakeBridge.instances[0].closed is True


def test_consult_role_uses_the_active_prompt_registry_version_when_edited(monkeypatch, tmp_path):
    # Fase 13 (extensión de cobertura del Prompt Registry): una edición real
    # vía prompt_registry.save_new_version (mismo camino que /n8n/prompts)
    # tiene que llegar de verdad al system prompt real con el que se llama
    # al LLM del rol, sin reiniciar nada — mismo criterio que los otros ~20
    # prompts ya cubiertos.
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    prompt_registry.save_new_version("executive_board_cto", "system prompt editado a mano", CTO_CONFIG.system_prompt)
    llm = _FakeLLM(tool_to_call=None)

    process.consult_role(CTO_CONFIG, "pregunta", llm)

    assert llm.received_system == "system prompt editado a mano"


def test_consult_role_falls_back_to_the_hardcoded_default_when_never_edited(monkeypatch, tmp_path):
    monkeypatch.setattr(prompt_registry, "PROMPTS_PATH", tmp_path / "prompts.json")
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    llm = _FakeLLM(tool_to_call=None)

    process.consult_role(CTO_CONFIG, "pregunta", llm)

    assert llm.received_system == CTO_CONFIG.system_prompt


def test_consult_role_degrades_honestly_without_calling_any_tool(monkeypatch):
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    llm = _FakeLLM(tool_to_call=None)

    result = process.consult_role(CTO_CONFIG, "pregunta", llm)

    # basis='hecho' con FUENTE vacía (nunca llamó a nada) se degrada a
    # 'inferencia' — el parser ya lo garantiza, este test confirma que el
    # flujo real de consult_role no lo evita de otra forma.
    assert result["opinions"][0]["basis"] == "inferencia"


def test_consult_role_prepends_upstream_context_to_the_system_prompt(monkeypatch):
    # Fase 17 (ADR 0158): cuando este rol corre en una stage posterior a
    # otra, el texto de la stage anterior tiene que llegar de verdad al
    # system prompt real con el que se llama al LLM.
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    llm = _FakeLLM(tool_to_call=None)

    process.consult_role(CTO_CONFIG, "pregunta", llm, upstream_context="Postura previa de coo: foco en X")

    assert llm.received_system.startswith(CTO_CONFIG.system_prompt)
    assert "Postura previa de coo: foco en X" in llm.received_system


def test_consult_role_without_upstream_context_never_touches_the_system_prompt(monkeypatch):
    _FakeBridge.instances = []
    monkeypatch.setattr(process, "_MCPToolBridge", _FakeBridge)
    llm = _FakeLLM(tool_to_call=None)

    process.consult_role(CTO_CONFIG, "pregunta", llm, upstream_context=None)

    assert llm.received_system == CTO_CONFIG.system_prompt
