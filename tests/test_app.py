import pytest
from fastapi.testclient import TestClient

import app as app_module
from snarf.memory.episodic import EpisodicMemory

TEST_PASSWORD = "test-password-for-pytest"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # app_module.orchestrator es un singleton creado al importar el módulo;
    # se fuerza acá su estado a "sin credenciales" y memoria descartable,
    # sin importar qué haya en el .env real del proyecto.
    monkeypatch.setattr(app_module.orchestrator, "_memory", EpisodicMemory(path=tmp_path / "memory.jsonl"))
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
    monkeypatch.setattr(app_module.stt, "_api_key", None)
    monkeypatch.setattr(app_module.tts, "_api_key", None)
    monkeypatch.setenv("SNARF_ACCESS_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    with TestClient(app_module.app) as c:
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


def test_transcribe_rejects_too_short_audio(client, monkeypatch):
    # Con credenciales (simuladas) presentes, el guard de tamaño mínimo debe
    # cortar antes de siquiera intentar llamar a la API de ElevenLabs.
    monkeypatch.setattr(app_module.stt, "_api_key", "fake-key-for-test")
    res = client.post("/transcribe", files={"file": ("audio.webm", b"short", "audio/webm")})
    assert res.status_code == 200
    assert res.json() == {"transcript": ""}


def test_tts_without_credentials_returns_no_audio(client):
    res = client.post("/tts", json={"text": "hola"})
    assert res.status_code == 200
    assert res.json() == {"audio_base64": None}


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


def test_dashboard_summary_reports_google_connected_when_token_exists(client, tmp_path, monkeypatch):
    tokens_dir = tmp_path / "tokens"
    tokens_dir.mkdir()
    (tokens_dir / f"{app_module.DEFAULT_USER_ID}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_module, "GOOGLE_TOKENS_DIR", tokens_dir)

    res = client.get("/dashboard/summary")
    assert res.status_code == 200
    assert res.json()["capabilities"]["google_connected"] is True


def test_dashboard_preferences_defaults_before_any_save(client, tmp_path, monkeypatch):
    from snarf.runtime import dashboard_prefs

    monkeypatch.setattr(dashboard_prefs, "PREFS_DIR", tmp_path / "prefs")
    res = client.get("/dashboard/preferences")
    assert res.status_code == 200
    data = res.json()
    assert data["panel_order"] == ["system", "conversations", "memory", "drive", "gmail", "calendar", "youtube"]
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


def test_gmail_digest_refresh_degrades_gracefully_on_error(client, connected_google_token, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("falló la interpretación")

    monkeypatch.setattr(app_module.orchestrator.gmail_digest, "refresh", boom)
    res = client.post("/dashboard/widgets/gmail/digest/refresh")
    assert res.status_code == 200
    assert res.json() == {"connected": True, "error": "falló la interpretación"}


