from types import SimpleNamespace

import pytest

from snarf.runtime import google_identity


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_email_returns_the_real_email_from_google(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse({"email": "persona@gmail.com", "email_verified": True})

    monkeypatch.setattr(google_identity.requests, "get", fake_get)
    creds = SimpleNamespace(token="tok-real")

    email = google_identity.fetch_email(creds)

    assert email == "persona@gmail.com"
    assert captured["url"] == google_identity.USERINFO_ENDPOINT
    assert captured["headers"] == {"Authorization": "Bearer tok-real"}


def test_fetch_email_raises_when_google_never_returns_an_email(monkeypatch):
    monkeypatch.setattr(google_identity.requests, "get", lambda *a, **k: _FakeResponse({}))
    with pytest.raises(RuntimeError):
        google_identity.fetch_email(SimpleNamespace(token="tok"))


def test_fetch_email_propagates_a_real_http_error(monkeypatch):
    monkeypatch.setattr(google_identity.requests, "get", lambda *a, **k: _FakeResponse({}, status_code=401))
    with pytest.raises(RuntimeError):
        google_identity.fetch_email(SimpleNamespace(token="tok-invalido"))


def test_user_id_for_email_is_stable_for_the_same_account():
    assert google_identity.user_id_for_email("Persona@Gmail.com") == google_identity.user_id_for_email("persona@gmail.com")


def test_user_id_for_email_sanitizes_unsafe_filesystem_characters():
    user_id = google_identity.user_id_for_email("Persona Real/../etc@Gmail.com")
    assert "/" not in user_id
    assert ".." not in user_id  # ningún input puede reconstruir un path traversal real


def test_user_id_for_email_never_produces_a_path_traversal_via_pathlib(tmp_path):
    from pathlib import Path

    user_id = google_identity.user_id_for_email("x/../../../etc/passwd@gmail.com")
    resolved = (tmp_path / user_id).resolve()
    assert resolved.parent == tmp_path.resolve()  # se queda DENTRO de tmp_path, nunca escapa
