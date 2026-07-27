import pytest
from fastapi.testclient import TestClient

import app as app_module
from snarf.memory.episodic import EpisodicMemory
from snarf.runtime.web_auth import (
    SESSION_COOKIE_NAME,
    create_session_token,
    verify_session_token,
)

CORRECT_PASSWORD = "correct-password"


@pytest.fixture
def raw_client(tmp_path, monkeypatch):
    """Cliente SIN login automático — para probar el propio flujo de auth,
    a diferencia de test_app.py que asume una sesión ya iniciada."""
    monkeypatch.setattr(app_module.orchestrator, "_memory", EpisodicMemory(path=tmp_path / "memory.jsonl"))
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
    monkeypatch.setenv("SNARF_ACCESS_PASSWORD", CORRECT_PASSWORD)
    monkeypatch.setenv("SESSION_SECRET", "a-test-secret")
    with TestClient(app_module.app) as c:
        yield c


def test_root_redirects_to_login_when_not_authenticated(raw_client):
    res = raw_client.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == "/login"


def test_protected_endpoint_rejects_without_session_cookie(raw_client):
    res = raw_client.post("/send", json={"text": "hola"})
    assert res.status_code == 401


def test_login_with_wrong_password_is_rejected(raw_client):
    res = raw_client.post("/login", json={"password": "incorrecta"})
    assert res.status_code == 401
    assert SESSION_COOKIE_NAME not in raw_client.cookies


def test_login_with_correct_password_grants_full_access(raw_client):
    login_res = raw_client.post("/login", json={"password": CORRECT_PASSWORD})
    assert login_res.status_code == 200
    assert SESSION_COOKIE_NAME in raw_client.cookies

    root_res = raw_client.get("/")
    assert root_res.status_code == 200
    assert "Snarf" in root_res.text

    send_res = raw_client.post("/send", json={"text": "hola"})
    assert send_res.status_code == 200


def test_logout_revokes_access(raw_client):
    raw_client.post("/login", json={"password": CORRECT_PASSWORD})
    raw_client.post("/logout")
    res = raw_client.post("/send", json={"text": "hola"})
    assert res.status_code == 401


def test_tampered_session_cookie_is_rejected(raw_client):
    raw_client.post("/login", json={"password": CORRECT_PASSWORD})
    raw_client.cookies.set(SESSION_COOKIE_NAME, raw_client.cookies[SESSION_COOKIE_NAME] + "tampered")
    res = raw_client.post("/send", json={"text": "hola"})
    assert res.status_code == 401


def test_login_fails_closed_without_session_secret(tmp_path, monkeypatch):
    # _client debe forzarse a None ANTES de instanciar TestClient: entrar al
    # context manager dispara el hook de startup (orchestrator.warmup()), que
    # sin esto haría una llamada real a la API de Anthropic.
    monkeypatch.setattr(app_module.orchestrator, "_memory", EpisodicMemory(path=tmp_path / "memory.jsonl"))
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
    monkeypatch.setenv("SNARF_ACCESS_PASSWORD", CORRECT_PASSWORD)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with TestClient(app_module.app) as c:
        res = c.post("/login", json={"password": CORRECT_PASSWORD})
        assert res.status_code == 503


def test_login_fails_closed_without_access_password_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.orchestrator, "_memory", EpisodicMemory(path=tmp_path / "memory.jsonl"))
    monkeypatch.setattr(app_module.orchestrator._llm, "_client", None)
    monkeypatch.delenv("SNARF_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("SESSION_SECRET", "a-test-secret")
    with TestClient(app_module.app) as c:
        res = c.post("/login", json={"password": "cualquier-cosa"})
        assert res.status_code == 401


def test_create_and_verify_session_token_roundtrip():
    token = create_session_token("a-secret", "fundador")
    assert verify_session_token("a-secret", token) == "fundador"


def test_verify_session_token_rejects_wrong_secret():
    token = create_session_token("secret-a", "fundador")
    assert verify_session_token("secret-b", token) is None


def test_verify_session_token_rejects_garbage():
    assert verify_session_token("a-secret", "esto-no-es-un-token-real") is None
