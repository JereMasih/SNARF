import pytest
import requests

from snarf.capabilities.discord import Discord


def _configure(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-real")
    monkeypatch.setenv("DISCORD_GUILD_ID", "guild-1")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "channel-1")


def test_unavailable_without_full_real_config(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("DISCORD_CHANNEL_ID", raising=False)
    assert Discord().available is False


def test_unavailable_with_only_the_token_and_no_guild_or_channel(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-real")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.delenv("DISCORD_CHANNEL_ID", raising=False)
    assert Discord().available is False


def test_available_with_full_real_config(monkeypatch):
    _configure(monkeypatch)
    assert Discord().available is True


def test_send_message_raises_without_real_config(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        Discord().send_message("hola")


class _FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_send_message_posts_to_the_configured_channel(monkeypatch):
    _configure(monkeypatch)
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse({"id": "msg-1"})

    monkeypatch.setattr(requests, "post", fake_post)

    result = Discord().send_message("hola comunidad")

    assert captured["url"] == "https://discord.com/api/v10/channels/channel-1/messages"
    assert captured["json"] == {"content": "hola comunidad"}
    assert result == {"id": "msg-1", "channel_id": "channel-1", "content": "hola comunidad"}


def test_list_recent_messages_parses_a_real_shaped_response(monkeypatch):
    _configure(monkeypatch)

    def fake_get(url, headers, params, timeout):
        return _FakeResponse(
            [{"id": "m1", "author": {"username": "jere"}, "content": "hola", "timestamp": "2026-08-05T00:00:00Z"}]
        )

    monkeypatch.setattr(requests, "get", fake_get)

    messages = Discord().list_recent_messages(limit=10)

    assert messages == [{"id": "m1", "author": "jere", "content": "hola", "timestamp": "2026-08-05T00:00:00Z"}]


def test_guild_member_count_reads_the_real_approximate_count(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse({"approximate_member_count": 42}))
    assert Discord().guild_member_count() == 42
