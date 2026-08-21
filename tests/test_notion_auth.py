from types import SimpleNamespace

import pytest

from snarf.capabilities import notion_auth as module
from snarf.capabilities.notion_auth import NotionAuth


def fake_response(json_data, status_code=200):
    def raise_for_status():
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code}")

    return SimpleNamespace(raise_for_status=raise_for_status, json=lambda: json_data, status_code=status_code)


def test_client_credentials_available_requires_both_env_vars(monkeypatch):
    monkeypatch.delenv("NOTION_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("NOTION_OAUTH_CLIENT_SECRET", raising=False)
    assert module.client_credentials_available() is False

    monkeypatch.setenv("NOTION_OAUTH_CLIENT_ID", "client-1")
    assert module.client_credentials_available() is False

    monkeypatch.setenv("NOTION_OAUTH_CLIENT_SECRET", "secret-1")
    assert module.client_credentials_available() is True


def test_build_authorization_url_includes_real_params(monkeypatch):
    monkeypatch.setenv("NOTION_OAUTH_CLIENT_ID", "client-1")
    url = module.build_authorization_url("https://snarf.example/callback", "nonce-1")
    assert url.startswith("https://api.notion.com/v1/oauth/authorize?")
    assert "client_id=client-1" in url
    assert "response_type=code" in url
    assert "owner=user" in url
    assert "state=nonce-1" in url
    assert "redirect_uri=https" in url


def test_exchange_code_sends_basic_auth_and_grant_type(monkeypatch):
    monkeypatch.setenv("NOTION_OAUTH_CLIENT_ID", "client-1")
    monkeypatch.setenv("NOTION_OAUTH_CLIENT_SECRET", "secret-1")
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json})
        return fake_response({"access_token": "token-1", "workspace_name": "Mi Workspace"})

    monkeypatch.setattr(module.requests, "post", fake_post)
    result = module.exchange_code("https://snarf.example/callback", "code-1")

    assert result == {"access_token": "token-1", "workspace_name": "Mi Workspace"}
    assert calls[0]["url"] == "https://api.notion.com/v1/oauth/token"
    assert calls[0]["headers"]["Authorization"].startswith("Basic ")
    assert calls[0]["json"] == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": "https://snarf.example/callback",
    }


def test_save_and_load_token_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module.save_token("fundador", {"access_token": "token-1", "workspace_name": "W"})
    assert module.load_token("fundador") == {"access_token": "token-1", "workspace_name": "W"}


def test_load_token_returns_none_when_never_connected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert module.load_token("nunca-conectado") is None


def test_tokens_are_namespaced_per_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    module.save_token("fundador", {"access_token": "token-fundador"})
    module.save_token("otro-usuario", {"access_token": "token-otro"})

    assert module.load_token("fundador")["access_token"] == "token-fundador"
    assert module.load_token("otro-usuario")["access_token"] == "token-otro"


def test_notion_auth_available_reflects_client_credentials(monkeypatch):
    monkeypatch.delenv("NOTION_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("NOTION_OAUTH_CLIENT_SECRET", raising=False)
    assert NotionAuth("fundador").available is False

    monkeypatch.setenv("NOTION_OAUTH_CLIENT_ID", "client-1")
    monkeypatch.setenv("NOTION_OAUTH_CLIENT_SECRET", "secret-1")
    assert NotionAuth("fundador").available is True


def test_notion_auth_connected_and_access_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    auth = NotionAuth("fundador")
    assert auth.connected is False
    assert auth.access_token() is None

    module.save_token("fundador", {"access_token": "token-real", "workspace_name": "Workspace Real"})
    assert auth.connected is True
    assert auth.access_token() == "token-real"
    assert auth.workspace_name() == "Workspace Real"
