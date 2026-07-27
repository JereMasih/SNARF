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
