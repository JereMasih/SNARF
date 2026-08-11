import json
from types import SimpleNamespace

import pytest

from snarf.capabilities import google_auth


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(google_auth, "TOKENS_DIR", tmp_path / "tokens")
    monkeypatch.setattr(google_auth, "CLIENT_SECRET_PATH", tmp_path / "google_client_secret.json")


def _write_fake_client_secret(path):
    path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "fake-client-id.apps.googleusercontent.com",
                    "client_secret": "fake-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["https://example.com/google/oauth/callback"],
                }
            }
        ),
        encoding="utf-8",
    )


def test_client_secret_available_reflects_the_real_file():
    assert google_auth.client_secret_available() is False
    _write_fake_client_secret(google_auth.CLIENT_SECRET_PATH)
    assert google_auth.client_secret_available() is True


def test_build_authorization_url_points_to_google_and_carries_the_real_state():
    _write_fake_client_secret(google_auth.CLIENT_SECRET_PATH)
    url = google_auth.build_authorization_url("https://example.com/google/oauth/callback", "real-state-123")
    assert url.startswith("https://accounts.google.com/o/oauth2/")
    assert "state=real-state-123" in url
    assert "client_id=fake-client-id" in url


def test_exchange_code_calls_fetch_token_and_returns_credentials(monkeypatch):
    _write_fake_client_secret(google_auth.CLIENT_SECRET_PATH)
    fake_creds = SimpleNamespace(to_json=lambda: json.dumps({"token": "real-token"}))

    class _FakeFlow:
        def __init__(self):
            self.credentials = fake_creds
            self.fetch_token_calls = []

        def fetch_token(self, **kwargs):
            self.fetch_token_calls.append(kwargs)

    fake_flow = _FakeFlow()
    monkeypatch.setattr(google_auth.Flow, "from_client_secrets_file", classmethod(lambda cls, *a, **k: fake_flow))

    result = google_auth.exchange_code(
        "https://example.com/google/oauth/callback", "state-real", "https://example.com/google/oauth/callback?code=abc&state=state-real"
    )

    assert result is fake_creds
    assert fake_flow.fetch_token_calls == [
        {"authorization_response": "https://example.com/google/oauth/callback?code=abc&state=state-real"}
    ]


def test_save_token_writes_the_real_credentials_json():
    creds = SimpleNamespace(to_json=lambda: json.dumps({"token": "abc123"}))
    google_auth.save_token("usuario_de_prueba", creds)
    saved = google_auth.token_path("usuario_de_prueba")
    assert saved.exists()
    assert json.loads(saved.read_text(encoding="utf-8")) == {"token": "abc123"}


def test_credentials_raises_a_clear_error_when_never_connected():
    auth = google_auth.GoogleAuth("usuario_sin_conectar")
    with pytest.raises(RuntimeError, match="no está conectado"):
        auth.credentials()


def test_credentials_reads_a_real_stored_valid_token(monkeypatch):
    auth = google_auth.GoogleAuth("usuario_conectado")
    google_auth.token_path("usuario_conectado").parent.mkdir(parents=True, exist_ok=True)

    fake_creds = SimpleNamespace(valid=True, expired=False, refresh_token="rt", to_json=lambda: "{}")
    monkeypatch.setattr(
        google_auth.Credentials, "from_authorized_user_file", classmethod(lambda cls, *a, **k: fake_creds)
    )
    google_auth.token_path("usuario_conectado").write_text("{}", encoding="utf-8")

    result = auth.credentials()
    assert result is fake_creds


def test_connected_property_reflects_whether_a_token_file_exists():
    auth = google_auth.GoogleAuth("usuario_x")
    assert auth.connected is False
    google_auth.save_token("usuario_x", SimpleNamespace(to_json=lambda: "{}"))
    assert auth.connected is True
