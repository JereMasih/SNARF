import pytest
from fastapi.testclient import TestClient

import app as app_module
from snarf.memory.audio_store import AudioStore
from snarf.memory.episodic import EpisodicMemory
from snarf.executive import specialist as executive_board_module
from snarf.specialists import dashboard_curator as dashboard_curator_module
from snarf.telemetry import activity_log, events, input_log, input_preprocessing, usage_tracker
from snarf.voice.providers.kokoro_tts import KokoroTTS
from snarf.voice.providers.local_stt import LocalWhisperSTT

TEST_PASSWORD = "test-password-for-pytest"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # app_module.orchestrator es un singleton creado al importar el módulo;
    # se fuerza acá su estado a "sin credenciales" y memoria descartable,
    # sin importar qué haya en el .env real del proyecto.
    monkeypatch.setattr(
        app_module.orchestrator,
        "_memory",
        EpisodicMemory(path=tmp_path / "memory.jsonl", project_links_path=tmp_path / "conversation_projects.json", titles_path=tmp_path / "conversation_titles.json"),
    )
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
    # _title_llm es una Capacidad de LLM SEPARADA (modelo barato, ver
    # generate_conversation_title) — /send la dispara sola como background
    # task en el primer turno de cualquier conversación, así que sin este
    # neutralizado los tests de /send dispararían llamadas reales.
    monkeypatch.setattr(app_module.orchestrator._title_llm, "_client", None)
    # Fuerza TODA la capa de voz a "nada disponible" sin importar credenciales
    # reales del .env ni si el contenedor Docker de Kokoro está corriendo en
    # esta máquina — los tests nunca deben depender de un servicio externo
    # real (ver KokoroTTS.available, que sí hace una request HTTP real).
    monkeypatch.setattr(app_module.voice_router._stt("groq"), "_api_key", None)
    monkeypatch.setattr(LocalWhisperSTT, "available", property(lambda self: False))
    monkeypatch.setattr(KokoroTTS, "available", property(lambda self: False))
    monkeypatch.setattr(app_module.voice_router._tts("elevenlabs_premium")._capability, "_api_key", None)
    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "_api_key", None)
    monkeypatch.setattr(app_module, "audio_store", AudioStore(directory=tmp_path / "audio"))
    monkeypatch.setattr(usage_tracker, "DEFAULT_PATH", tmp_path / "usage_log.jsonl")
    monkeypatch.setattr(activity_log, "DEFAULT_PATH", tmp_path / "activity_log.jsonl")
    monkeypatch.setattr(input_log, "DEFAULT_PATH", tmp_path / "input_log.jsonl")
    # activity_log/usage_tracker/input_log ya redirigidos arriba, pero cada
    # uno también emite el evento unificado (Fase 1 del plan de HUD) hacia
    # events.DEFAULT_PATH — sin este monkeypatch, ese archivo real se sigue
    # poluyendo con datos sintéticos de test aunque los otros tres no.
    monkeypatch.setattr(events, "DEFAULT_PATH", tmp_path / "telemetry_events.jsonl")
    monkeypatch.setattr(input_preprocessing, "DEFAULT_PATH", tmp_path / "input_preprocessing_log.jsonl")
    # dashboard_curator es un Specialist con estado en disco propio (Vista
    # HUD) — sin este redirect, estos tests leerían el cache REAL de
    # producción (data/dashboard_curation/), como pasó de verdad: el loop
    # periódico corrió con datos reales después de un restart de esta misma
    # sesión y dejó un archivo real ahí, haciendo fallar un test que asumía
    # cache vacío (mismo tipo de fuga que ADR 0085).
    monkeypatch.setattr(dashboard_curator_module, "CACHE_DIR", tmp_path / "dashboard_curation")
    monkeypatch.setattr(dashboard_curator_module, "TEMPLATE_PROPOSALS_PATH", tmp_path / "dashboard_template_proposals.json")
    # Inteligencia Ejecutiva (ver ADR 0094/0098): mismo motivo que
    # dashboard_curator arriba — estado en disco propio, nunca el cache real
    # de producción.
    monkeypatch.setattr(executive_board_module, "CACHE_DIR", tmp_path / "executive_board")
    # Skill Factory (ver ADR 0095/0102): _proposals_dir es un atributo de
    # instancia (no una constante de módulo, a diferencia de arriba) — sin
    # este redirect, estos tests leerían/escribirían el registro REAL de
    # producción (data/skill_proposals/), como pasó de verdad: un intento
    # real de construir "Procesador de PDFs" (falló por crédito real
    # agotado de Claude Code) quedó ahí y hacía fallar un test que asumía
    # el registro vacío — mismo tipo de fuga que ADR 0085.
    monkeypatch.setattr(app_module.orchestrator.skill_factory, "_proposals_dir", tmp_path / "skill_proposals")
    monkeypatch.setenv("SNARF_ACCESS_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    with TestClient(app_module.app, base_url="https://testserver") as c:
        # Estos tests no son sobre auth (eso está en test_web_auth.py); se
        # loguea de una vez con el flujo real para que el resto del archivo
        # pruebe el comportamiento normal de la app ya autenticada.
        login_res = c.post("/login", json={"password": TEST_PASSWORD})
        assert login_res.status_code == 200
        yield c


def test_index_serves_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Snarf" in res.text


def test_status_reports_availability_flags(client):
    res = client.get("/status")
    assert res.status_code == 200
    assert res.json() == {"stt_available": False, "tts_available": False, "llm_available": False}


def test_send_echo_mode_roundtrip(client):
    res = client.post("/send", json={"text": "hola", "conversation_id": "abc"})
    assert res.status_code == 200
    assert "hola" in res.json()["response"]


def test_send_schedules_title_generation_only_on_the_first_turn(client, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.orchestrator, "generate_conversation_title", lambda cid: calls.append(cid))
    client.post("/send", json={"text": "primer mensaje", "conversation_id": "conv-titulo"})
    assert calls == ["conv-titulo"]
    client.post("/send", json={"text": "segundo mensaje", "conversation_id": "conv-titulo"})
    assert calls == ["conv-titulo"]  # no se vuelve a disparar en turnos siguientes


def test_send_returns_the_deliverable_field_when_the_llm_produces_one(client, monkeypatch):
    from snarf.capabilities.anthropic_llm import LLMResponse

    monkeypatch.setattr(app_module.orchestrator._llm, "_client", object())  # available=True
    monkeypatch.setattr(
        app_module.orchestrator._llm,
        "generate",
        lambda **kwargs: LLMResponse(text="acá tenés el plan", speech="te armé el plan", deliverable="solo el plan"),
    )
    res = client.post("/send", json={"text": "haceme un plan", "conversation_id": "conv-deliverable"})
    assert res.status_code == 200
    assert res.json()["deliverable"] == "solo el plan"


def test_send_tags_the_memory_entry_with_the_conversations_assigned_project(client):
    # Proyectos Mark II: la asociación es persistente (assign_conversation),
    # ya no un parámetro por mensaje en /send.
    app_module.orchestrator.memory.assign_conversation("conv-proj", "proj-1")
    client.post("/send", json={"text": "hola", "conversation_id": "conv-proj"})
    entry = app_module.orchestrator.memory.get_conversation("conv-proj")[0]
    assert entry["project_id"] == "proj-1"


def test_send_records_a_text_input_log_entry(client):
    client.post("/send", json={"text": "hola", "conversation_id": "abc"})
    entries = input_log.recent()
    assert len(entries) == 1
    assert entries[0]["channel"] == "text"


def test_conversations_list_reflects_appended_entries(client):
    client.post("/send", json={"text": "primer mensaje", "conversation_id": "conv-1"})
    res = client.get("/conversations")
    assert res.status_code == 200
    convs = res.json()
    assert any(c["conversation_id"] == "conv-1" for c in convs)


def test_get_single_conversation(client):
    client.post("/send", json={"text": "hola", "conversation_id": "conv-2"})
    res = client.get("/conversations/conv-2")
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    assert entries[0]["input"] == "hola"


def test_transcribe_without_credentials_returns_empty_transcript(client):
    res = client.post("/transcribe", files={"file": ("audio.webm", b"x" * 5000, "audio/webm")})
    assert res.status_code == 200
    assert res.json() == {"transcript": ""}


def test_transcribe_records_a_voice_input_log_entry_for_real_audio(client, monkeypatch):
    groq = app_module.voice_router._stt("groq")
    monkeypatch.setattr(groq, "_api_key", "fake-key-for-test")
    monkeypatch.setattr(groq, "transcribe", lambda *a, **kw: "texto transcripto")
    client.post("/transcribe", files={"file": ("audio.webm", b"x" * 5000, "audio/webm")})
    entries = input_log.recent()
    assert len(entries) == 1
    assert entries[0]["channel"] == "voice"


def test_transcribe_reports_an_explicit_error_when_stt_itself_fails(client, monkeypatch):
    """Antes de este fix, un fallo real del servicio (cuota agotada, red)
    volvía indistinguible de un silencio genuino — la interfaz le decía al
    usuario "no se escuchó nada" cuando en realidad el micrófono funcionó
    perfecto y el servicio de voz fue el que falló."""
    groq = app_module.voice_router._stt("groq")
    monkeypatch.setattr(groq, "_api_key", "fake-key-for-test")

    def boom(*a, **kw):
        raise RuntimeError("Groq STT 401: quota_exceeded")

    monkeypatch.setattr(groq, "transcribe", boom)
    res = client.post("/transcribe", files={"file": ("audio.webm", b"x" * 5000, "audio/webm")})
    assert res.status_code == 200
    data = res.json()
    assert data["transcript"] == ""
    assert data["error"]


def test_transcribe_rejects_too_short_audio(client, monkeypatch):
    # Con credenciales (simuladas) presentes, el guard de tamaño mínimo debe
    # cortar antes de siquiera intentar llamar a la API de Groq.
    monkeypatch.setattr(app_module.voice_router._stt("groq"), "_api_key", "fake-key-for-test")
    res = client.post("/transcribe", files={"file": ("audio.webm", b"short", "audio/webm")})
    assert res.status_code == 200
    assert res.json() == {"transcript": ""}


def test_transcribe_does_not_record_input_log_entry_for_too_short_audio(client, monkeypatch):
    monkeypatch.setattr(app_module.voice_router._stt("groq"), "_api_key", "fake-key-for-test")
    client.post("/transcribe", files={"file": ("audio.webm", b"short", "audio/webm")})
    assert input_log.recent() == []


def test_transcribe_stores_the_real_audio_and_returns_its_id(client, monkeypatch):
    groq = app_module.voice_router._stt("groq")
    monkeypatch.setattr(groq, "_api_key", "fake-key-for-test")
    monkeypatch.setattr(groq, "transcribe", lambda *a, **kw: "texto transcripto")
    res = client.post("/transcribe", files={"file": ("audio.webm", b"x" * 5000, "audio/webm")})
    audio_id = res.json()["audio_id"]
    assert audio_id.endswith(".webm")
    assert app_module.audio_store.path_for(audio_id) is not None


def test_transcribe_stores_the_audio_even_when_stt_itself_fails(client, monkeypatch):
    # La nota de voz real sigue siendo reproducible en el chat aunque el
    # servicio de transcripción falle — solo se pierde la transcripción, no
    # el audio en sí.
    groq = app_module.voice_router._stt("groq")
    monkeypatch.setattr(groq, "_api_key", "fake-key-for-test")

    def boom(*a, **kw):
        raise RuntimeError("Groq STT 401: quota_exceeded")

    monkeypatch.setattr(groq, "transcribe", boom)
    res = client.post("/transcribe", files={"file": ("audio.webm", b"x" * 5000, "audio/webm")})
    audio_id = res.json()["audio_id"]
    assert app_module.audio_store.path_for(audio_id) is not None


def test_get_audio_serves_a_stored_file(client):
    audio_id = app_module.audio_store.save(b"fake audio bytes", "webm")
    res = client.get(f"/audio/{audio_id}")
    assert res.status_code == 200
    assert res.content == b"fake audio bytes"
    assert res.headers["content-type"] == "audio/webm"


def test_get_audio_404s_for_an_unknown_or_unsafe_id(client):
    assert client.get("/audio/does-not-exist.mp3").status_code == 404
    assert client.get("/audio/..%2f..%2fetc%2fpasswd").status_code == 404


def test_send_persists_the_input_audio_id_on_the_memory_entry(client):
    client.post("/send", json={"text": "hola", "conversation_id": "conv-voice", "input_audio_id": "abc123.webm"})
    entry = app_module.orchestrator.memory.get_conversation("conv-voice")[0]
    assert entry["input_audio_id"] == "abc123.webm"


def test_tts_caches_by_content_and_does_not_resynthesize_the_same_text(client, monkeypatch):
    # Sin tier explícito, /tts usa el tier 'local' (kokoro) — se fuerza
    # disponible y se stubea speak() para no depender del contenedor real.
    kokoro = app_module.voice_router._tts("kokoro")
    monkeypatch.setattr(type(kokoro), "available", property(lambda self: True))
    calls = []
    monkeypatch.setattr(kokoro, "speak", lambda text, voice=None, audio_format="mp3": calls.append(text) or b"real audio bytes")

    first = client.post("/tts", json={"text": "hola de nuevo"})
    second = client.post("/tts", json={"text": "hola de nuevo"})

    assert first.json() == second.json()
    assert len(calls) == 1  # la segunda vez sirvió del caché, no volvió a pagar una síntesis real


def test_tts_without_credentials_returns_no_audio(client):
    res = client.post("/tts", json={"text": "hola"})
    assert res.status_code == 200
    assert res.json() == {"audio_base64": None, "audio_id": None}


def test_dashboard_summary_reports_capabilities_and_memory_stats(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tmp_path / "tokens")
    client.post("/send", json={"text": "primer mensaje", "conversation_id": "conv-1"})
    client.post("/send", json={"text": "segundo mensaje", "conversation_id": "conv-2"})

    res = client.get("/dashboard/summary")
    assert res.status_code == 200
    data = res.json()

    assert data["user_id"] == app_module.DEFAULT_USER_ID
    assert data["capabilities"] == {
        "llm": False,
        "stt": False,
        "tts": False,
        "google_connected": False,
    }
    assert data["memory"]["total_messages"] == 2
    assert data["memory"]["total_conversations"] == 2
    assert len(data["memory"]["activity_by_day"]) == 14
    assert data["cost"]["total_usd"] == 0
    assert data["cost"]["total_calls"] == 0


def test_dashboard_summary_reports_google_connected_when_token_exists(client, tmp_path, monkeypatch):
    tokens_dir = tmp_path / "tokens"
    tokens_dir.mkdir()
    (tokens_dir / f"{app_module.DEFAULT_USER_ID}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tokens_dir)

    res = client.get("/dashboard/summary")
    assert res.status_code == 200
    assert res.json()["capabilities"]["google_connected"] is True


def test_dashboard_brain_returns_nodes_and_events(client, monkeypatch):
    monkeypatch.setattr(
        app_module.orchestrator.drive_indexer,
        "manifest_summary",
        lambda: {"indexed": 0, "error": 0, "skipped_unsupported": 0, "total": 0},
    )
    activity_log.record("drive_list_files", "ok")
    usage_tracker.record_voyage_call("voyage-4-lite", tokens=100)

    res = client.get("/dashboard/brain")
    assert res.status_code == 200
    data = res.json()

    assert "server_time" in data
    assert data["nodes"]["drive"]["count"] == 1
    assert data["nodes"]["knowledge"]["count"] == 1
    assert len(data["events"]) == 2


def test_dashboard_brain_since_param_filters_to_new_events_only(client, monkeypatch):
    monkeypatch.setattr(
        app_module.orchestrator.drive_indexer,
        "manifest_summary",
        lambda: {"indexed": 0, "error": 0, "skipped_unsupported": 0, "total": 0},
    )
    activity_log.record("drive_list_files", "ok")
    first = client.get("/dashboard/brain").json()

    activity_log.record("gmail_list_messages", "ok")
    second = client.get(f"/dashboard/brain?since={first['server_time']}").json()

    assert len(second["events"]) == 1
    assert second["events"][0]["node"] == "gmail_read"


def test_dashboard_telemetry_feed_returns_events_with_verb_and_summary(client):
    activity_log.record("drive_list_files", "ok", duration_ms=12.0)
    res = client.get("/dashboard/telemetry_feed")
    assert res.status_code == 200
    data = res.json()
    assert "server_time" in data
    assert len(data["events"]) == 1
    ev = data["events"][0]
    assert ev["nodo"] == "drive"
    assert ev["verbo"] == "hojeando el Drive"
    assert ev["resumen"] == "drive_list_files"
    assert ev["estado"] == "completo"


def test_dashboard_telemetry_feed_since_param_filters_to_new_events_only(client):
    activity_log.record("drive_list_files", "ok")
    first = client.get("/dashboard/telemetry_feed").json()

    activity_log.record("gmail_list_messages", "ok")
    second = client.get(f"/dashboard/telemetry_feed?since={first['server_time']}").json()

    assert len(second["events"]) == 1
    assert second["events"][0]["nodo"] == "gmail_read"


def test_dashboard_dock_priority_ranks_real_nodes_by_recent_activity(client):
    activity_log.record("drive_list_files", "ok")
    res = client.get("/dashboard/dock_priority")
    assert res.status_code == 200
    body = res.json()
    assert "server_time" in body
    top = body["ranking"][0]
    assert top["nodo"] == "drive"
    assert top["score"] > 0


def test_dashboard_dock_priority_surfaces_cost_alert_when_threshold_crossed(client):
    from snarf.telemetry import relevance

    usage_tracker.record_anthropic_call("claude-sonnet-5", 1_000_000, 200_000)  # cruza el umbral de $1/día con margen
    res = client.get("/dashboard/dock_priority")
    ranking = res.json()["ranking"]
    assert ranking[0]["nodo"] == "cost"
    assert ranking[0]["score"] == relevance.COST_ALERT_SCORE


def test_dashboard_widget_summaries_includes_real_activity(client):
    activity_log.record("drive_list_files", "ok")
    res = client.get("/dashboard/widget_summaries")
    assert res.status_code == 200
    body = res.json()
    assert "server_time" in body
    widget = next(w for w in body["widgets"] if w["node_id"] == "drive")
    assert widget["count_total"] == 1
    assert widget["curator_caption"] is None  # el Especialista todavía no curó nada — honesto, no un placeholder


def test_dashboard_widget_summaries_excludes_nodes_without_real_activity(client):
    res = client.get("/dashboard/widget_summaries")
    assert res.json()["widgets"] == []


def test_dashboard_widget_summaries_merges_real_curator_captions(client, monkeypatch):
    import app as app_module

    activity_log.record("drive_list_files", "ok")
    monkeypatch.setattr(
        app_module.dashboard_curator,
        "cached_curation",
        lambda: {"generated_at": 1.0, "headline": "x", "node_captions": {"drive": "una nota real curada"}},
    )
    res = client.get("/dashboard/widget_summaries")
    widget = next(w for w in res.json()["widgets"] if w["node_id"] == "drive")
    assert widget["curator_caption"] == "una nota real curada"


def test_dashboard_widget_summaries_includes_mechanical_default_template(client):
    # Antes de cualquier curación real, un widget todavía recibe una
    # plantilla — el default mecánico de su size_tier, nunca un placeholder
    # inventado por el curador.
    from snarf.telemetry import widget_templates

    activity_log.record("drive_list_files", "ok")
    res = client.get("/dashboard/widget_summaries")
    widget = next(w for w in res.json()["widgets"] if w["node_id"] == "drive")
    assert widget["size_tier"] == "large"  # único widget activo -> rank 0
    assert widget["template"] == widget_templates.DEFAULT_TEMPLATE_BY_TIER["large"]


def test_dashboard_widget_summaries_merges_real_curator_template(client, monkeypatch):
    import app as app_module

    activity_log.record("drive_list_files", "ok")  # único widget activo -> rank 0 -> size_tier "large"
    monkeypatch.setattr(
        app_module.dashboard_curator,
        "cached_curation",
        lambda: {
            "generated_at": 1.0, "headline": "x",
            "node_captions": {"drive": "una nota real curada"},
            "node_templates": {"drive": "deep_chart"},  # plantilla GRANDE válida, mismo tier que "drive" acá
        },
    )
    res = client.get("/dashboard/widget_summaries")
    widget = next(w for w in res.json()["widgets"] if w["node_id"] == "drive")
    assert widget["template"] == "deep_chart"


def test_dashboard_widget_summaries_discards_stale_cached_template_from_a_higher_tier(client, monkeypatch):
    # Regresión de un bug real encontrado con Playwright: un nodo curado
    # mientras era "medium" (con una plantilla de 320px) puede decaer a
    # "small" en un poll posterior (el ranking se recalcula en vivo, la
    # curación no) — usar la plantilla vieja sin validar metía una card
    # grande en el espacio angosto reservado para widgets chicos.
    import app as app_module
    from snarf.telemetry import widget_templates

    activity_log.record("drive_list_files", "ok")  # único widget activo -> rank 0 -> size_tier "large"
    monkeypatch.setattr(
        app_module.dashboard_curator,
        "cached_curation",
        lambda: {
            "generated_at": 1.0, "headline": "x",
            "node_captions": {"drive": "x"},
            "node_templates": {"drive": "standard_wide"},  # plantilla MEDIANA, inválida para "large"
        },
    )
    res = client.get("/dashboard/widget_summaries")
    widget = next(w for w in res.json()["widgets"] if w["node_id"] == "drive")
    assert widget["size_tier"] == "large"
    assert widget["template"] == widget_templates.DEFAULT_TEMPLATE_BY_TIER["large"]


def test_dashboard_widget_templates_endpoint_returns_all_24(client):
    from snarf.telemetry import widget_templates

    res = client.get("/dashboard/widget_templates")
    assert res.status_code == 200
    templates = res.json()["templates"]
    assert len(templates) == 24
    assert set(templates.keys()) == set(widget_templates.WIDGET_TEMPLATES.keys())
    tiers = {t["tier"] for t in templates.values()}
    assert tiers == {"small", "medium", "large"}


def test_dashboard_template_proposals_endpoint_is_read_only_and_empty_by_default(client):
    # La fixture `client` ya aísla TEMPLATE_PROPOSALS_PATH a un tmp_path.
    res = client.get("/dashboard/template_proposals")
    assert res.status_code == 200
    assert res.json()["proposals"] == []


def test_dashboard_curation_is_honest_before_any_refresh(client):
    res = client.get("/dashboard/curation")
    assert res.status_code == 200
    body = res.json()
    assert body["headline"] is None
    assert body["generated_at"] is None
    assert body["curating"] is False


def test_dashboard_node_activity_filters_to_a_single_node(client):
    activity_log.record("drive_list_files", "ok")
    activity_log.record("gmail_list_messages", "ok")
    res = client.get("/dashboard/node_activity/drive")
    assert res.status_code == 200
    node_events = res.json()["events"]
    assert len(node_events) == 1
    assert node_events[0]["nodo"] == "drive"


def test_dashboard_node_activity_since_param_filters_to_new_events_only(client):
    activity_log.record("drive_list_files", "ok")
    first = client.get("/dashboard/node_activity/drive").json()
    activity_log.record("drive_read_file", "ok")
    second = client.get(f"/dashboard/node_activity/drive?since={first['server_time']}").json()
    assert len(second["events"]) == 1


def test_dashboard_input_efficiency_reports_real_overhead(client):
    input_preprocessing.record("c1", "hola", system_chars=400, history_chars=0, history_entries=0)
    res = client.get("/dashboard/input_efficiency")
    assert res.status_code == 200
    body = res.json()
    assert body["recent"][0]["input_original"] == "hola"
    assert body["recent"][0]["overhead_ratio"] > 1
    assert body["summary"]["turns"] == 1


def test_dashboard_preferences_defaults_before_any_save(client, tmp_path, monkeypatch):
    from snarf.runtime import dashboard_prefs

    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path / "prefs")
    res = client.get("/dashboard/preferences")
    assert res.status_code == 200
    data = res.json()
    assert data["panel_order"] == [
        "history", "brain", "system", "cost", "chat",
        "conversations", "memory", "usage", "drive", "gmail", "calendar", "youtube",
    ]
    assert all(data["visible_widgets"].values())


def test_dashboard_preferences_put_then_get_roundtrip(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tmp_path / "tokens")
    from snarf.runtime import dashboard_prefs

    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path / "prefs")

    put_res = client.put(
        "/dashboard/preferences",
        json={"visible_widgets": {"drive": False}, "panel_order": ["youtube", "gmail"]},
    )
    assert put_res.status_code == 200
    assert put_res.json()["visible_widgets"]["drive"] is False

    get_res = client.get("/dashboard/preferences")
    assert get_res.json() == put_res.json()


def test_dashboard_preferences_span_roundtrip_via_http(client, tmp_path, monkeypatch):
    from snarf.runtime import dashboard_prefs

    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path / "prefs")
    put_res = client.put(
        "/dashboard/preferences",
        json={"widget_options": {"drive": {"col_span": 8, "row_span": 14}}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["widget_options"]["drive"] == {"col_span": 8, "row_span": 14}

    get_res = client.get("/dashboard/preferences")
    assert get_res.json()["widget_options"]["drive"] == {"col_span": 8, "row_span": 14}


def test_dashboard_preferences_http_cannot_hide_chat_or_history(client, tmp_path, monkeypatch):
    from snarf.runtime import dashboard_prefs

    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path / "prefs")
    put_res = client.put(
        "/dashboard/preferences",
        json={"visible_widgets": {"chat": False, "history": False}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["visible_widgets"]["chat"] is True
    assert put_res.json()["visible_widgets"]["history"] is True


def test_personality_preferences_defaults_before_any_save(client, tmp_path, monkeypatch):
    from snarf.runtime import personality_prefs

    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path / "personality_prefs")
    res = client.get("/personality/preferences")
    assert res.status_code == 200
    assert res.json() == {"sarcasm_level": 7.5}


def test_personality_preferences_put_then_get_roundtrip(client, tmp_path, monkeypatch):
    from snarf.runtime import personality_prefs

    monkeypatch.setattr(personality_prefs, "PREFS_DIR", tmp_path / "personality_prefs")
    put_res = client.put("/personality/preferences", json={"sarcasm_level": 3})
    assert put_res.status_code == 200
    assert put_res.json()["sarcasm_level"] == 3.0

    get_res = client.get("/personality/preferences")
    assert get_res.json() == put_res.json()


def test_llm_routing_defaults_before_any_save(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    res = client.get("/llm-routing")
    assert res.status_code == 200
    assert res.json()["routing"] == llm_routing.DEFAULT_ROUTING


def test_llm_routing_put_then_get_roundtrip(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    # El PUT real llama a orchestrator.refresh_llm_routing(), que reconstruye
    # _llm/_title_llm sobre el singleton REAL y compartido entre tests — sin
    # esto, un GeminiLLM real quedaba pegado ahí después de este test y
    # contaminaba todos los que corren después en la misma sesión de pytest
    # (bug real encontrado corriendo la suite completa, no solo este test).
    monkeypatch.setattr(app_module.orchestrator, "_llm", app_module.orchestrator._llm)
    monkeypatch.setattr(app_module.orchestrator, "_title_llm", app_module.orchestrator._title_llm)
    put_res = client.put("/llm-routing", json={"orchestrator": {"provider": "gemini", "model": "gemini-3-pro-preview"}})
    assert put_res.status_code == 200
    assert put_res.json()["routing"]["orchestrator"] == {"provider": "gemini", "model": "gemini-3-pro-preview"}

    get_res = client.get("/llm-routing")
    assert get_res.json()["routing"] == put_res.json()["routing"]


def test_llm_routing_put_of_one_role_does_not_reset_the_others(client, tmp_path, monkeypatch):
    """Bug real encontrado en vivo (2026-08-05): el PUT solo manda el rol que
    cambió (ver persistLlmRouting en web/index.html), y save_routing()
    completa cualquier rol ausente del payload con DEFAULT_ROUTING — sin
    mergear primero con lo ya guardado, elegir un proveedor nuevo para UN rol
    desde Configuración reseteaba en silencio TODOS los demás roles."""
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.setattr(app_module.orchestrator, "_llm", app_module.orchestrator._llm)
    monkeypatch.setattr(app_module.orchestrator, "_title_llm", app_module.orchestrator._title_llm)

    client.put("/llm-routing", json={"gmail_digest": {"provider": "gemini", "model": "gemini-3-pro-preview"}})
    put_res = client.put("/llm-routing", json={"orchestrator": {"provider": "openai", "model": "gpt-5"}})

    routing = put_res.json()["routing"]
    assert routing["orchestrator"] == {"provider": "openai", "model": "gpt-5"}
    assert routing["gmail_digest"] == {"provider": "gemini", "model": "gemini-3-pro-preview"}


def test_llm_routing_reports_available_providers_from_real_env_vars(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "ROUTING_PATH", tmp_path / "llm_routing.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.get("/llm-routing")
    assert "gemini" not in res.json()["available_providers"]

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    res2 = client.get("/llm-routing")
    assert "gemini" in res2.json()["available_providers"]


def test_llm_fallback_events_empty_without_any_real_fallback(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    res = client.get("/llm-routing/fallback_events")
    assert res.status_code == 200
    assert res.json()["events"] == []
    assert isinstance(res.json()["server_time"], float)


def test_llm_fallback_events_reports_a_real_recorded_fallback(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    llm_routing._append_fallback_log(
        {
            "timestamp": 1000.0,
            "role": "dashboard_curator",
            "from": {"provider": "anthropic", "model": "claude-haiku-4-5"},
            "to": {"provider": "xai", "model": "grok-4-1-fast"},
            "error": "credit balance is too low",
        }
    )
    res = client.get("/llm-routing/fallback_events")
    events = res.json()["events"]
    assert len(events) == 1
    assert events[0]["role"] == "dashboard_curator"
    assert events[0]["to"]["provider"] == "xai"


def test_llm_fallback_events_filters_by_since(client, tmp_path, monkeypatch):
    from snarf.runtime import llm_routing

    monkeypatch.setattr(llm_routing, "FALLBACK_LOG_PATH", tmp_path / "llm_fallback_log.jsonl")
    llm_routing._append_fallback_log(
        {"timestamp": 100.0, "role": "old", "from": {}, "to": {}, "error": "e"}
    )
    llm_routing._append_fallback_log(
        {"timestamp": 200.0, "role": "new", "from": {}, "to": {}, "error": "e"}
    )
    res = client.get("/llm-routing/fallback_events?since=150")
    events = res.json()["events"]
    assert [e["role"] for e in events] == ["new"]


def test_profile_defaults_before_any_save(client, tmp_path, monkeypatch):
    from snarf.runtime import user_profile

    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path / "user_profile")
    res = client.get("/profile")
    assert res.status_code == 200
    assert res.json() == {"name": None}


def test_profile_put_then_get_roundtrip(client, tmp_path, monkeypatch):
    from snarf.runtime import user_profile

    monkeypatch.setattr(user_profile, "PREFS_DIR", tmp_path / "user_profile")
    put_res = client.put("/profile", json={"name": "Jere"})
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Jere"

    get_res = client.get("/profile")
    assert get_res.json() == put_res.json()


@pytest.fixture
def no_google_token(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tmp_path / "tokens")


@pytest.mark.parametrize("widget", ["drive", "gmail", "calendar", "youtube"])
def test_dashboard_widget_reports_not_connected_without_token(client, no_google_token, widget):
    res = client.get(f"/dashboard/widgets/{widget}")
    assert res.status_code == 200
    assert res.json() == {"connected": False}


@pytest.fixture
def connected_google_token(tmp_path, monkeypatch):
    tokens_dir = tmp_path / "tokens"
    tokens_dir.mkdir()
    (tokens_dir / f"{app_module.DEFAULT_USER_ID}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tokens_dir)


def test_dashboard_widget_usage_reports_real_metrics_per_vendor(client):
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1000, 500)
    usage_tracker.record_elevenlabs_tts_call(120)
    res = client.get("/dashboard/widgets/usage")
    assert res.status_code == 200
    vendors = res.json()["vendors"]
    assert vendors["anthropic"]["calls"] == 1
    assert vendors["anthropic"]["input_tokens"] == 1000
    assert vendors["anthropic"]["cost_usd"] > 0
    assert vendors["elevenlabs"]["characters"] == 120
    assert vendors["elevenlabs"]["cost_usd"] is None


def test_dashboard_cost_history_aggregates_by_day_agente_and_session(client):
    usage_tracker.record_anthropic_call("claude-sonnet-5", 1000, 500)
    res = client.get("/dashboard/cost_history")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"by_day", "by_agente", "by_session"}
    assert body["by_day"][0]["llamadas"] == 1
    # "llm" (Anthropic) es un nodo; su agente/tier real (brain.NODE_TIER) es
    # "capability" — no confundir nodo con agente acá.
    assert body["by_agente"][0]["key"] == "capability"
    assert body["by_agente"][0]["costo_usd"] > 0


def test_dashboard_widget_usage_includes_real_elevenlabs_subscription_when_available(client, monkeypatch):
    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "_api_key", "fake-key")
    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "_voice_id", "fake-voice")
    monkeypatch.setattr(
        app_module._elevenlabs_for_dashboard,
        "subscription_info",
        lambda: {"tier": "starter", "character_count": 1234, "character_limit": 30000},
    )
    usage_tracker.record_elevenlabs_tts_call(50)
    res = client.get("/dashboard/widgets/usage")
    subscription = res.json()["vendors"]["elevenlabs"]["subscription"]
    assert subscription == {"tier": "starter", "character_count": 1234, "character_limit": 30000}


def test_dashboard_widget_usage_reports_subscription_error_without_hiding_local_metrics(client, monkeypatch):
    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "_api_key", "fake-key")
    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "_voice_id", "fake-voice")

    def boom():
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(app_module._elevenlabs_for_dashboard, "subscription_info", boom)
    usage_tracker.record_elevenlabs_tts_call(50)
    res = client.get("/dashboard/widgets/usage")
    data = res.json()["vendors"]["elevenlabs"]
    assert data["characters"] == 50
    assert "401" in data["subscription_error"]


def test_dashboard_widget_drive_returns_recent_files(client, connected_google_token, monkeypatch):
    fake_files = [
        {"id": "1", "name": "viejo.txt", "modifiedTime": "2026-01-01T00:00:00Z"},
        {"id": "2", "name": "nuevo.txt", "modifiedTime": "2026-07-20T00:00:00Z"},
    ]
    monkeypatch.setattr(app_module.orchestrator.drive, "list_files", lambda **kwargs: list(fake_files))
    res = client.get("/dashboard/widgets/drive")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is True
    assert data["files"][0]["name"] == "nuevo.txt"


def test_dashboard_widget_gmail_returns_messages(client, connected_google_token, monkeypatch):
    fake_messages = [{"id": "1", "subject": "hola", "from": "a@b.com"}]
    monkeypatch.setattr(app_module.orchestrator.gmail, "list_messages", lambda **kwargs: fake_messages)
    res = client.get("/dashboard/widgets/gmail")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "messages": fake_messages}


def test_dashboard_widget_gmail_respects_max_results_param(client, connected_google_token, monkeypatch):
    received = {}
    monkeypatch.setattr(
        app_module.orchestrator.gmail,
        "list_messages",
        lambda **kwargs: received.update(kwargs) or [],
    )
    client.get("/dashboard/widgets/gmail?max_results=20")
    assert received == {"max_results": 20}


def test_dashboard_widget_gmail_clamps_out_of_range_max_results(client, connected_google_token, monkeypatch):
    received = {}
    monkeypatch.setattr(
        app_module.orchestrator.gmail,
        "list_messages",
        lambda **kwargs: received.update(kwargs) or [],
    )
    client.get("/dashboard/widgets/gmail?max_results=500")
    assert received == {"max_results": 20}


def test_dashboard_widget_calendar_returns_events(client, connected_google_token, monkeypatch):
    fake_events = [{"id": "1", "summary": "reunión", "start": "2026-08-01T10:00:00Z"}]
    monkeypatch.setattr(app_module.orchestrator.calendar, "list_upcoming_events", lambda **kwargs: fake_events)
    res = client.get("/dashboard/widgets/calendar")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "events": fake_events}


def test_dashboard_widget_youtube_returns_subscriptions(client, connected_google_token, monkeypatch):
    fake_subs = [{"channel": "Canal de prueba"}]
    monkeypatch.setattr(app_module.orchestrator.youtube, "list_subscriptions", lambda **kwargs: fake_subs)
    res = client.get("/dashboard/widgets/youtube")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "subscriptions": fake_subs}


def test_dashboard_widget_degrades_gracefully_on_api_error(client, connected_google_token, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("google api caída")

    monkeypatch.setattr(app_module.orchestrator.drive, "list_files", boom)
    res = client.get("/dashboard/widgets/drive")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "error": "google api caída"}


def test_gmail_digest_reports_not_connected_without_token(client, no_google_token):
    res = client.get("/dashboard/widgets/gmail/digest")
    assert res.status_code == 200
    assert res.json() == {"connected": False}


def test_gmail_digest_returns_none_before_any_refresh(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.gmail_digest, "cached_digest", lambda: None)
    res = client.get("/dashboard/widgets/gmail/digest")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "digest": None}


def test_gmail_digest_returns_cached_value(client, connected_google_token, monkeypatch):
    cached = {"generated_at": 123.0, "message_count": 2, "digest_text": "resumen"}
    monkeypatch.setattr(app_module.orchestrator.gmail_digest, "cached_digest", lambda: cached)
    res = client.get("/dashboard/widgets/gmail/digest")
    assert res.json() == {"connected": True, "digest": cached}


def test_gmail_digest_refresh_triggers_a_fresh_generation(client, connected_google_token, monkeypatch):
    fresh = {"generated_at": 999.0, "message_count": 3, "digest_text": "nuevo resumen"}
    monkeypatch.setattr(app_module.orchestrator.gmail_digest, "refresh", lambda **kw: fresh)
    res = client.post("/dashboard/widgets/gmail/digest/refresh")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "digest": fresh}


def test_calendar_brief_reports_not_connected_without_token(client, no_google_token):
    res = client.get("/dashboard/widgets/calendar/brief")
    assert res.status_code == 200
    assert res.json() == {"connected": False}


def test_calendar_brief_returns_none_before_any_refresh(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.calendar_brief, "cached_brief", lambda: None)
    res = client.get("/dashboard/widgets/calendar/brief")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "brief": None}


def test_calendar_brief_returns_cached_value(client, connected_google_token, monkeypatch):
    cached = {"generated_at": 123.0, "event_count": 2, "brief_text": "resumen"}
    monkeypatch.setattr(app_module.orchestrator.calendar_brief, "cached_brief", lambda: cached)
    res = client.get("/dashboard/widgets/calendar/brief")
    assert res.json() == {"connected": True, "brief": cached}


def test_calendar_brief_refresh_triggers_a_fresh_generation(client, connected_google_token, monkeypatch):
    fresh = {"generated_at": 999.0, "event_count": 3, "brief_text": "nuevo resumen"}
    monkeypatch.setattr(app_module.orchestrator.calendar_brief, "refresh", lambda **kw: fresh)
    res = client.post("/dashboard/widgets/calendar/brief/refresh")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "brief": fresh}


def test_calendar_brief_refresh_degrades_gracefully_on_error(client, connected_google_token, monkeypatch):
    def boom(**kw):
        raise RuntimeError("falla real de la API de Calendar")

    monkeypatch.setattr(app_module.orchestrator.calendar_brief, "refresh", boom)
    res = client.post("/dashboard/widgets/calendar/brief/refresh")
    assert res.status_code == 200
    assert res.json()["connected"] is True
    assert "error" in res.json()


def test_upload_file_without_google_connected_returns_400(client, no_google_token):
    res = client.post("/files/upload", files={"file": ("a.txt", b"contenido", "text/plain")})
    assert res.status_code == 400


def test_upload_file_saves_to_drive_and_indexes_it(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.document_publisher, "folder_id", lambda: "folder-1")
    monkeypatch.setattr(
        app_module.orchestrator.drive,
        "upload_file",
        lambda *a, **kw: {"id": "f1", "name": "a.txt", "mimeType": "text/plain", "modifiedTime": "t1", "webViewLink": "http://x"},
    )
    monkeypatch.setattr(app_module.orchestrator.drive_indexer, "index_file", lambda file, extra_metadata=None: {"status": "indexed"})

    res = client.post("/files/upload", files={"file": ("a.txt", b"contenido", "text/plain")})

    assert res.status_code == 200
    data = res.json()
    assert data["indexed"] is True
    assert data["webViewLink"] == "http://x"
    assert "analysis" not in data


def test_upload_file_records_a_file_input_log_entry_with_its_real_category(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.document_publisher, "folder_id", lambda: "folder-1")
    monkeypatch.setattr(
        app_module.orchestrator.drive,
        "upload_file",
        lambda *a, **kw: {"id": "f1", "name": "a.png", "mimeType": "image/png", "modifiedTime": "t1", "webViewLink": "http://x"},
    )
    monkeypatch.setattr(app_module.orchestrator.drive_indexer, "index_file", lambda file, extra_metadata=None: {"status": "indexed"})

    client.post("/files/upload", files={"file": ("a.png", b"contenido", "image/png")})

    entries = input_log.recent()
    assert len(entries) == 1
    assert entries[0]["channel"] == "file"
    assert entries[0]["category"] == "image"


def test_upload_image_returns_the_stored_analysis_text(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.document_publisher, "folder_id", lambda: "folder-1")
    monkeypatch.setattr(
        app_module.orchestrator.drive,
        "upload_file",
        lambda *a, **kw: {"id": "img1", "name": "foto.png", "mimeType": "image/png", "modifiedTime": "t1", "webViewLink": "http://x"},
    )
    monkeypatch.setattr(app_module.orchestrator.drive_indexer, "index_file", lambda file, extra_metadata=None: {"status": "indexed"})
    monkeypatch.setattr(app_module.orchestrator.drive_indexer, "get_indexed_text", lambda file_id: "una descripción real de la imagen")

    res = client.post("/files/upload", files={"file": ("foto.png", b"bytes-de-imagen", "image/png")})

    assert res.status_code == 200
    assert res.json()["analysis"] == "una descripción real de la imagen"


def test_upload_file_degrades_with_a_clear_error_when_drive_fails(client, connected_google_token, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator.document_publisher, "folder_id", lambda: "folder-1")

    def boom(*a, **kw):
        raise RuntimeError("drive caído")

    monkeypatch.setattr(app_module.orchestrator.drive, "upload_file", boom)

    res = client.post("/files/upload", files={"file": ("a.txt", b"x", "text/plain")})
    assert res.status_code == 502


def test_download_local_file_serves_real_bytes_from_disk(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "LOCAL_FILES_DATA_DIR", tmp_path)
    user_dir = tmp_path / app_module.DEFAULT_USER_ID
    user_dir.mkdir()
    (user_dir / "borrador.md").write_bytes(b"contenido real del borrador")

    res = client.get(f"/files/local/{app_module.DEFAULT_USER_ID}/borrador.md")

    assert res.status_code == 200
    assert res.content == b"contenido real del borrador"


def test_download_local_file_returns_404_when_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "LOCAL_FILES_DATA_DIR", tmp_path)
    res = client.get(f"/files/local/{app_module.DEFAULT_USER_ID}/no-existe.md")
    assert res.status_code == 404


def test_download_local_file_rejects_a_different_users_file(client):
    res = client.get("/files/local/otro_usuario/borrador.md")
    assert res.status_code == 403


def test_download_local_file_strips_directory_components_from_the_filename(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "LOCAL_FILES_DATA_DIR", tmp_path)
    secret_dir = tmp_path.parent / "secreto"
    secret_dir.mkdir(exist_ok=True)
    (secret_dir / "no_deberia_verse.txt").write_bytes(b"secreto")

    res = client.get(f"/files/local/{app_module.DEFAULT_USER_ID}/..%2Fsecreto%2Fno_deberia_verse.txt")

    assert res.status_code == 404


def test_gmail_digest_refresh_degrades_gracefully_on_error(client, connected_google_token, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("falló la interpretación")

    monkeypatch.setattr(app_module.orchestrator.gmail_digest, "refresh", boom)
    res = client.post("/dashboard/widgets/gmail/digest/refresh")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "error": "falló la interpretación"}


@pytest.fixture
def projects_fixture(tmp_path, monkeypatch, connected_google_token):
    from snarf.specialists import project_manager as module

    monkeypatch.setattr(module, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(app_module.orchestrator.drive, "get_or_create_folder", lambda name, parent_id=None: f"folder-{name}")
    # cached_summary()/file_count() de GET /projects/{id} llaman a Drive real
    # si no se mockea esto — sin costo/llamada real en tests.
    monkeypatch.setattr(app_module.orchestrator.drive, "iter_all_files", lambda query=None, page_size=200: iter([]))
    # ProjectManager ya no guarda una instancia fija de LLM (ver
    # _llm_factory) — sin ANTHROPIC_API_KEY en el entorno de test (conftest.py
    # la borra siempre), cualquier instancia que la factory resuelva ya nace
    # con available=False, sin costo real, sin necesitar mockear nada acá.


def test_list_projects_is_empty_before_any_creation(client, projects_fixture):
    res = client.get("/projects")
    assert res.status_code == 200
    assert res.json() == []


def test_create_project_requires_google_connected(client, no_google_token):
    res = client.post("/projects", json={"name": "Proyecto"})
    assert res.status_code == 400


def test_create_project_degrades_gracefully_on_drive_error(client, tmp_path, monkeypatch, connected_google_token):
    from snarf.specialists import project_manager as module

    monkeypatch.setattr(module, "PROJECTS_DIR", tmp_path / "projects")

    def boom(name, parent_id=None):
        raise RuntimeError("Drive no disponible")

    monkeypatch.setattr(app_module.orchestrator.drive, "get_or_create_folder", boom)
    res = client.post("/projects", json={"name": "Proyecto"})
    assert res.status_code == 502


def test_create_and_get_project_roundtrip(client, projects_fixture):
    create_res = client.post("/projects", json={"name": "Finanzas"})
    assert create_res.status_code == 200
    project_id = create_res.json()["id"]

    get_res = client.get(f"/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Finanzas"

    list_res = client.get("/projects")
    assert list_res.json()[0]["id"] == project_id


def test_get_project_returns_404_for_a_missing_project(client, projects_fixture):
    res = client.get("/projects/no-existe")
    assert res.status_code == 404


def test_set_project_prompt(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Newsletter"}).json()["id"]
    res = client.put(f"/projects/{project_id}/prompt", json={"prompt": "sos el asistente de este proyecto"})
    assert res.status_code == 200
    assert res.json()["prompt"] == "sos el asistente de este proyecto"


def test_project_task_roundtrip(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    added = client.post(f"/projects/{project_id}/tasks", json={"text": "primera tarea"})
    task_id = added.json()["tasks"][0]["id"]

    toggled = client.patch(f"/projects/{project_id}/tasks/{task_id}")
    assert toggled.json()["tasks"][0]["done"] is True

    deleted = client.delete(f"/projects/{project_id}/tasks/{task_id}")
    assert deleted.json()["tasks"] == []


def test_project_note_roundtrip(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    added = client.post(f"/projects/{project_id}/notes", json={"text": "una nota"})
    note_id = added.json()["notes"][0]["id"]

    deleted = client.delete(f"/projects/{project_id}/notes/{note_id}")
    assert deleted.json()["notes"] == []


def test_delete_project_without_confirmed_is_rejected(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    res = client.delete(f"/projects/{project_id}")
    assert res.status_code == 400
    assert client.get(f"/projects/{project_id}").status_code == 200  # sigue existiendo


def test_delete_project_with_confirmed_removes_it_and_never_touches_drive(client, projects_fixture, monkeypatch):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    delete_calls = []
    monkeypatch.setattr(app_module.orchestrator.drive, "delete_file", lambda file_id: delete_calls.append(file_id))

    res = client.delete(f"/projects/{project_id}?confirmed=true")
    assert res.status_code == 200
    assert client.get(f"/projects/{project_id}").status_code == 404
    assert delete_calls == []  # nunca se llamó a borrar nada real de Drive


def test_get_project_is_enriched_with_file_count_pending_tasks_and_conversations(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    client.post(f"/projects/{project_id}/tasks", json={"text": "pendiente"})
    done = client.post(f"/projects/{project_id}/tasks", json={"text": "hecha"})
    client.patch(f"/projects/{project_id}/tasks/{done.json()['tasks'][1]['id']}")
    app_module.orchestrator.memory.assign_conversation("conv-1", project_id)

    project = client.get(f"/projects/{project_id}").json()
    assert project["file_count"] == 0
    assert project["pending_task_count"] == 1
    assert [c["conversation_id"] for c in project["conversations"]] == ["conv-1"]
    assert project["summary"]  # se generó solo en el primer GET (cached_summary)


def test_get_project_conversations_endpoint(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    app_module.orchestrator.memory.assign_conversation("conv-1", project_id)
    res = client.get(f"/projects/{project_id}/conversations")
    assert res.status_code == 200
    assert [c["conversation_id"] for c in res.json()] == ["conv-1"]


def test_get_project_conversations_returns_404_for_a_missing_project(client, projects_fixture):
    res = client.get("/projects/no-existe/conversations")
    assert res.status_code == 404


def test_refresh_project_summary_endpoint(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    res = client.post(f"/projects/{project_id}/summary/refresh")
    assert res.status_code == 200
    assert res.json()["summary"]
    assert res.json()["summary_generated_at"] is not None


def test_refresh_project_summary_returns_404_for_a_missing_project(client, projects_fixture):
    res = client.post("/projects/no-existe/summary/refresh")
    assert res.status_code == 404


def test_assign_conversation_to_project_endpoint(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    res = client.put(f"/conversations/conv-1/project", json={"project_id": project_id})
    assert res.status_code == 200
    assert res.json() == {"conversation_id": "conv-1", "from_project_id": None, "to_project_id": project_id}
    assert app_module.orchestrator.memory.get_conversation_project("conv-1") == project_id


def test_assign_conversation_to_a_missing_project_returns_404(client, projects_fixture):
    res = client.put("/conversations/conv-1/project", json={"project_id": "no-existe"})
    assert res.status_code == 404


def test_unassign_conversation_from_project_endpoint(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    client.put(f"/conversations/conv-1/project", json={"project_id": project_id})
    res = client.delete("/conversations/conv-1/project")
    assert res.status_code == 200
    assert res.json() == {"conversation_id": "conv-1", "from_project_id": project_id, "to_project_id": None}
    assert app_module.orchestrator.memory.get_conversation_project("conv-1") is None


def test_conversations_list_excludes_conversations_assigned_to_a_project(client, projects_fixture):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]
    client.post("/send", json={"text": "general", "conversation_id": "conv-general"})
    client.post("/send", json={"text": "de proyecto", "conversation_id": "conv-proj"})
    client.put(f"/conversations/conv-proj/project", json={"project_id": project_id})

    res = client.get("/conversations")
    assert [c["conversation_id"] for c in res.json()] == ["conv-general"]


def test_upload_with_project_id_uploads_to_the_project_folder_and_tags_the_index(
    client, connected_google_token, projects_fixture, monkeypatch
):
    project_id = client.post("/projects", json={"name": "Proyecto"}).json()["id"]

    upload_calls = []
    monkeypatch.setattr(
        app_module.orchestrator.drive,
        "upload_file",
        lambda *a, **kw: upload_calls.append(kw) or {"id": "f1", "name": "a.pdf", "mimeType": "application/pdf", "modifiedTime": "t1", "webViewLink": "http://x"},
    )
    index_calls = []
    monkeypatch.setattr(
        app_module.orchestrator.drive_indexer,
        "index_file",
        lambda file, extra_metadata=None: index_calls.append(extra_metadata) or {"status": "indexed"},
    )

    res = client.post("/files/upload", files={"file": ("a.pdf", b"contenido", "application/pdf")}, data={"project_id": project_id})
    assert res.status_code == 200
    project = client.get(f"/projects/{project_id}").json()
    assert upload_calls[0]["parent_id"] == project["drive_folder_id"]
    assert index_calls[0] == {"project_id": project_id}


def test_dashboard_executive_board_widget_is_none_before_any_consult(client):
    res = client.get("/dashboard/widgets/executive_board")
    assert res.status_code == 200
    assert res.json() == {"consult": None}


def test_dashboard_executive_board_consult_persists_and_the_widget_reflects_it(client, monkeypatch):
    monkeypatch.setattr(
        app_module.orchestrator.executive_board,
        "_llm_factory_for_role",
        lambda role: object(),
    )

    def fake_consult_role(role_config, question, llm, repo_root):
        return {"headline": f"{role_config.role}: {question}", "opinions": [], "raw": ""}

    import snarf.executive.specialist as specialist_module

    monkeypatch.setattr(specialist_module, "consult_role", fake_consult_role)

    res = client.post("/dashboard/widgets/executive_board/consult", json={"question": "¿abrimos YouTube?", "roles": ["cto"]})
    assert res.status_code == 200
    assert res.json()["roles"]["cto"]["headline"] == "cto: ¿abrimos YouTube?"

    widget = client.get("/dashboard/widgets/executive_board").json()
    assert widget["consult"]["question"] == "¿abrimos YouTube?"


def test_dashboard_executive_board_consult_requires_a_question(client):
    res = client.post("/dashboard/widgets/executive_board/consult", json={})
    assert res.status_code == 200
    assert "error" in res.json()


