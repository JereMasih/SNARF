import pytest
from fastapi.testclient import TestClient

import app as app_module
from snarf.memory.audio_store import AudioStore
from snarf.memory.episodic import EpisodicMemory
from snarf.telemetry import activity_log, input_log, usage_tracker
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
        EpisodicMemory(path=tmp_path / "memory.jsonl", project_links_path=tmp_path / "conversation_projects.json"),
    )
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
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
    monkeypatch.setattr(app_module.orchestrator.projects._llm, "_client", None)  # sin costo real en tests


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


