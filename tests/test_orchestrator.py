import pytest

from snarf.core.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    # Aísla la memoria episódica del proyecto real: cada test corre en su
    # propio directorio temporal, nunca escribe en data/episodic_memory.jsonl.
    monkeypatch.chdir(tmp_path)
    return Orchestrator()


def test_echo_mode_without_api_key_and_persists_to_memory(orchestrator):
    response = orchestrator.handle("text", "hola snarf", conversation_id="c1")
    assert "hola snarf" in response
    assert "modo eco" in response
    assert orchestrator.memory.get_conversation("c1")[0]["response"] == response


def test_handle_tool_reports_unknown_tool(orchestrator):
    result = orchestrator._handle_tool("herramienta_inexistente", {})
    assert result == {"error": "herramienta desconocida: herramienta_inexistente"}


def test_handle_tool_catches_handler_exceptions(orchestrator, monkeypatch):
    def boom(_input):
        raise RuntimeError("fallo simulado")

    monkeypatch.setitem(orchestrator._tool_handlers, "list_conversations", boom)
    result = orchestrator._handle_tool("list_conversations", {})
    assert result == {"error": "fallo simulado"}


# (nombre de la tool, atributo de capacidad en Orchestrator, método real, input base)
HIGH_IMPACT_TOOLS = [
    ("gmail_send_message", "_gmail", "send_message", {"to": "a@b.com", "subject": "s", "body": "b"}),
    (
        "calendar_create_event",
        "_calendar",
        "create_event",
        {"summary": "s", "start_iso": "2026-01-01T10:00:00Z", "end_iso": "2026-01-01T11:00:00Z"},
    ),
    ("calendar_create_calendar", "_calendar", "create_calendar", {"summary": "Nuevo calendario"}),
    ("calendar_delete_calendar", "_calendar", "delete_calendar", {"calendar_id": "cal-1"}),
    ("calendar_delete_event", "_calendar", "delete_event", {"event_id": "ev-1"}),
    (
        "calendar_move_event",
        "_calendar",
        "move_event",
        {"event_id": "ev-1", "source_calendar_id": "a", "destination_calendar_id": "b"},
    ),
    ("gmail_delete_label", "_gmail", "delete_label", {"label_id": "lbl-1"}),
    ("drive_delete_file", "_drive", "delete_file", {"file_id": "f-1"}),
]


@pytest.mark.parametrize("tool_name, capability_attr, method_name, base_input", HIGH_IMPACT_TOOLS)
def test_high_impact_tool_requires_explicit_confirmation(
    orchestrator, monkeypatch, tool_name, capability_attr, method_name, base_input
):
    """Artículo VII de CONSTITUTION.md ('Prueba de Alto Impacto'): ninguna
    acción de alto impacto puede ejecutarse sin confirmación explícita en un
    paso posterior. Verifica, para las 8 herramientas de alto impacto, que
    (1) sin confirmed=True nunca se llama a la capacidad real, y
    (2) con confirmed=True sí se llama, exactamente una vez."""
    calls = []
    capability = getattr(orchestrator, capability_attr)
    monkeypatch.setattr(capability, method_name, lambda *a, **kw: calls.append((a, kw)) or {"id": "x"})

    pending = orchestrator._handle_tool(tool_name, dict(base_input))
    assert pending["status"] == "pending_confirmation"
    assert calls == []

    orchestrator._handle_tool(tool_name, {**base_input, "confirmed": True})
    assert len(calls) == 1


def test_gmail_summarize_inbox_returns_cached_digest_when_present(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "digest_text": "ya interpretado"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: cached)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: (_ for _ in ()).throw(AssertionError("no debería refrescar")))
    assert orchestrator._handle_tool("gmail_summarize_inbox", {}) == cached


def test_gmail_summarize_inbox_refreshes_when_nothing_cached(orchestrator, monkeypatch):
    fresh = {"generated_at": 2.0, "message_count": 1, "digest_text": "recién generado"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: None)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("gmail_summarize_inbox", {}) == fresh


def test_gmail_summarize_inbox_force_refresh_ignores_cache(orchestrator, monkeypatch):
    cached = {"generated_at": 1.0, "message_count": 2, "digest_text": "viejo"}
    fresh = {"generated_at": 2.0, "message_count": 3, "digest_text": "nuevo"}
    monkeypatch.setattr(orchestrator.gmail_digest, "cached_digest", lambda: cached)
    monkeypatch.setattr(orchestrator.gmail_digest, "refresh", lambda **kw: fresh)
    assert orchestrator._handle_tool("gmail_summarize_inbox", {"force_refresh": True}) == fresh
