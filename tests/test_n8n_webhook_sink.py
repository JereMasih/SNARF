from snarf.telemetry import n8n_webhook_sink


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_is_configured_false_without_the_env_var(monkeypatch):
    monkeypatch.delenv(n8n_webhook_sink.URL_ENV_VAR, raising=False)
    assert n8n_webhook_sink.is_configured() is False


def test_is_configured_true_with_the_env_var_set(monkeypatch):
    monkeypatch.setenv(n8n_webhook_sink.URL_ENV_VAR, "http://127.0.0.1:5678/webhook/real")
    assert n8n_webhook_sink.is_configured() is True


def test_install_is_a_noop_without_the_env_var(monkeypatch):
    monkeypatch.delenv(n8n_webhook_sink.URL_ENV_VAR, raising=False)
    assert n8n_webhook_sink.install() is False
    assert n8n_webhook_sink.health()["configured"] is False


def test_install_registers_a_dispatcher_subscriber_when_configured(monkeypatch):
    monkeypatch.setenv(n8n_webhook_sink.URL_ENV_VAR, "http://127.0.0.1:5678/webhook/real")
    assert n8n_webhook_sink.install() is True
    assert n8n_webhook_sink.health()["configured"] is True

    from snarf.telemetry import dispatcher

    assert any(s.name == n8n_webhook_sink.SUBSCRIBER_NAME for s in dispatcher.subscribers())


def test_publish_to_webhook_posts_the_full_event_as_json(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(200)

    monkeypatch.setenv(n8n_webhook_sink.URL_ENV_VAR, "http://127.0.0.1:5678/webhook/real")
    monkeypatch.setattr(n8n_webhook_sink.requests, "post", fake_post)

    event = {"event_type": "tool.finished", "skill": "drive_list_files"}
    n8n_webhook_sink.publish_to_webhook(event)

    assert captured["url"] == "http://127.0.0.1:5678/webhook/real"
    assert captured["json"] == event
    assert n8n_webhook_sink.health()["sent"] == 1


def test_publish_to_webhook_swallows_a_real_connection_error(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise ConnectionError("n8n caído (simulado)")

    monkeypatch.setenv(n8n_webhook_sink.URL_ENV_VAR, "http://127.0.0.1:5678/webhook/real")
    monkeypatch.setattr(n8n_webhook_sink.requests, "post", fake_post)

    n8n_webhook_sink.publish_to_webhook({"event_type": "tool.finished"})  # nunca debe levantar

    health = n8n_webhook_sink.health()
    assert health["failed"] == 1
    assert "ConnectionError" in health["last_error"]


def test_publish_to_webhook_is_a_noop_without_the_env_var(monkeypatch):
    monkeypatch.delenv(n8n_webhook_sink.URL_ENV_VAR, raising=False)
    n8n_webhook_sink.publish_to_webhook({"event_type": "tool.finished"})
    assert n8n_webhook_sink.health()["sent"] == 0


def test_health_reports_not_configured_by_default():
    assert n8n_webhook_sink.health() == {"configured": False, "sent": 0, "failed": 0, "last_error": None}
