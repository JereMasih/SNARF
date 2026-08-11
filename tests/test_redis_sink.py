import json

from snarf.telemetry import redis_sink


class _FakeRedisClient:
    def __init__(self, *, raise_on_xadd=False):
        self.calls = []
        self._raise_on_xadd = raise_on_xadd

    def xadd(self, key, fields, maxlen=None, approximate=None):
        if self._raise_on_xadd:
            raise ConnectionError("Redis caído (simulado)")
        self.calls.append({"key": key, "fields": fields, "maxlen": maxlen, "approximate": approximate})


def test_is_configured_false_without_the_env_var(monkeypatch):
    monkeypatch.delenv(redis_sink.URL_ENV_VAR, raising=False)
    assert redis_sink.is_configured() is False


def test_is_configured_true_with_the_env_var_set(monkeypatch):
    monkeypatch.setenv(redis_sink.URL_ENV_VAR, "redis://localhost:6379/0")
    assert redis_sink.is_configured() is True


def test_install_is_a_noop_without_the_env_var(monkeypatch):
    monkeypatch.delenv(redis_sink.URL_ENV_VAR, raising=False)
    assert redis_sink.install() is False
    assert redis_sink.health()["configured"] is False


def test_install_registers_a_client_and_a_dispatcher_subscriber_when_configured(monkeypatch):
    import redis as real_redis

    fake_client = _FakeRedisClient()
    monkeypatch.setenv(redis_sink.URL_ENV_VAR, "redis://localhost:6379/0")
    monkeypatch.setattr(real_redis.Redis, "from_url", classmethod(lambda cls, *a, **k: fake_client))

    assert redis_sink.install() is True
    assert redis_sink.health()["configured"] is True

    from snarf.telemetry import dispatcher

    assert any(s.name == redis_sink.SUBSCRIBER_NAME for s in dispatcher.subscribers())


def test_publish_to_stream_calls_xadd_with_the_full_event_as_json(monkeypatch):
    import redis as real_redis

    fake_client = _FakeRedisClient()
    monkeypatch.setenv(redis_sink.URL_ENV_VAR, "redis://localhost:6379/0")
    monkeypatch.setattr(real_redis.Redis, "from_url", classmethod(lambda cls, *a, **k: fake_client))
    redis_sink.install()

    event = {"event_type": "tool.finished", "trace_id": "t1", "nodo": "drive", "origin_pid": 123, "skill": "drive_list_files"}
    redis_sink.publish_to_stream(event)

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["key"] == redis_sink.STREAM_KEY
    assert call["maxlen"] == redis_sink.MAXLEN
    assert call["approximate"] is True
    assert call["fields"]["event_type"] == "tool.finished"
    assert call["fields"]["trace_id"] == "t1"
    assert call["fields"]["nodo"] == "drive"
    assert json.loads(call["fields"]["json"]) == event
    assert redis_sink.health()["published"] == 1


def test_publish_to_stream_swallows_a_real_connection_error(monkeypatch):
    import redis as real_redis

    fake_client = _FakeRedisClient(raise_on_xadd=True)
    monkeypatch.setenv(redis_sink.URL_ENV_VAR, "redis://localhost:6379/0")
    monkeypatch.setattr(real_redis.Redis, "from_url", classmethod(lambda cls, *a, **k: fake_client))
    redis_sink.install()

    redis_sink.publish_to_stream({"event_type": "tool.finished"})  # nunca debe levantar

    health = redis_sink.health()
    assert health["failed"] == 1
    assert "ConnectionError" in health["last_error"]


def test_publish_to_stream_is_a_noop_when_never_installed():
    redis_sink.publish_to_stream({"event_type": "tool.finished"})  # sin client -> no-op
    assert redis_sink.health()["published"] == 0


def test_health_reports_not_configured_by_default():
    assert redis_sink.health() == {"configured": False, "published": 0, "failed": 0, "last_error": None}
