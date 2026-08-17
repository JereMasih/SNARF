from snarf.telemetry import n8n_live_canvas_sink


class _FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def _turn_started(trace_id="trace-1", event_id="event-1"):
    return {
        "event_type": "workflow.started", "skill": "turn", "trace_id": trace_id,
        "event_id": event_id, "parent_event_id": None,
    }


def _turn_finished(trace_id="trace-1"):
    return {"event_type": "workflow.finished", "skill": "turn", "trace_id": trace_id, "event_id": "event-1"}


def _some_stage_event(trace_id="trace-1", event_type="agent.started", skill="cto"):
    return {"event_type": event_type, "skill": skill, "trace_id": trace_id, "event_id": "event-x"}


def test_is_configured_false_without_the_env_var(monkeypatch):
    monkeypatch.delenv(n8n_live_canvas_sink.ENABLED_ENV_VAR, raising=False)
    assert n8n_live_canvas_sink.is_configured() is False


def test_is_configured_true_with_the_env_var_set(monkeypatch):
    monkeypatch.setenv(n8n_live_canvas_sink.ENABLED_ENV_VAR, "1")
    assert n8n_live_canvas_sink.is_configured() is True


def test_install_is_a_noop_without_the_env_var(monkeypatch):
    monkeypatch.delenv(n8n_live_canvas_sink.ENABLED_ENV_VAR, raising=False)
    assert n8n_live_canvas_sink.install() is False
    assert n8n_live_canvas_sink.health()["configured"] is False


def test_install_registers_a_dispatcher_subscriber_when_configured(monkeypatch):
    monkeypatch.setenv(n8n_live_canvas_sink.ENABLED_ENV_VAR, "1")
    assert n8n_live_canvas_sink.install() is True
    assert n8n_live_canvas_sink.health()["configured"] is True

    from snarf.telemetry import dispatcher

    assert any(s.name == n8n_live_canvas_sink.SUBSCRIBER_NAME for s in dispatcher.subscribers())


def test_handle_event_ignores_a_non_turn_event_with_no_known_trace(monkeypatch):
    n8n_live_canvas_sink.handle_event(_some_stage_event())
    health = n8n_live_canvas_sink.health()
    assert health["started"] == 0
    assert health["active_traces"] == 0


def test_handle_event_starts_a_new_execution_on_turn_started(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(200, body=[{"executionId": "exec-42"}])

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))

    assert captured["url"] == n8n_live_canvas_sink._trigger_url()
    health = n8n_live_canvas_sink.health()
    assert health["started"] == 1
    assert health["active_traces"] == 1


def test_handle_event_resumes_the_right_execution_for_a_known_trace(monkeypatch):
    posts = []

    def fake_post(url, json=None, timeout=None):
        posts.append(url)
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        return _FakeResponse(200)

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))

    assert posts[-1] == n8n_live_canvas_sink._resume_url("exec-42")
    assert n8n_live_canvas_sink.health()["resumed"] == 1


def test_handle_event_never_resumes_more_than_the_real_stage_count(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        return _FakeResponse(200)

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    for _ in range(n8n_live_canvas_sink._MAX_STAGE_RESUMES + 3):
        n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))

    assert n8n_live_canvas_sink.health()["resumed"] == n8n_live_canvas_sink._MAX_STAGE_RESUMES


def test_handle_event_forgets_the_trace_once_the_turn_finishes(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        return _FakeResponse(200)

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    n8n_live_canvas_sink.handle_event(_turn_finished(trace_id="trace-1"))

    assert n8n_live_canvas_sink.health()["active_traces"] == 0


def test_handle_event_two_concurrent_traces_never_cross_talk(monkeypatch):
    trigger_calls = {"trace-a": "exec-a", "trace-b": "exec-b"}
    posts = []

    def fake_post(url, json=None, timeout=None):
        posts.append(url)
        if url == n8n_live_canvas_sink._trigger_url():
            trace_id = json["trace_id"]
            return _FakeResponse(200, body=[{"executionId": trigger_calls[trace_id]}])
        return _FakeResponse(200)

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-a"))
    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-b"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-a"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-b"))

    assert n8n_live_canvas_sink._resume_url("exec-a") in posts
    assert n8n_live_canvas_sink._resume_url("exec-b") in posts
    assert n8n_live_canvas_sink.health()["resumed"] == 2


def test_handle_event_swallows_a_real_connection_error_starting_a_trace(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        raise ConnectionError("n8n caído (simulado)")

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))  # nunca debe levantar

    health = n8n_live_canvas_sink.health()
    assert health["failed"] == 1
    assert "ConnectionError" in health["last_error"]
    assert health["active_traces"] == 0


def test_handle_event_swallows_a_real_connection_error_resuming_a_trace(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        raise ConnectionError("n8n caído a mitad de turno (simulado)")

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))

    health = n8n_live_canvas_sink.health()
    assert health["failed"] == 1
    assert health["resumed"] == 0


def test_sweep_stale_drops_traces_older_than_the_real_wait_timeout(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return _FakeResponse(200, body=[{"executionId": "exec-42"}])

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)
    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    assert n8n_live_canvas_sink.health()["active_traces"] == 1

    # Simula que pasó más tiempo que el timeout real del nodo Wait — sin
    # tocar time.time() real, movemos el reloj del propio estado guardado.
    n8n_live_canvas_sink._traces["trace-1"]["updated_at"] -= n8n_live_canvas_sink._MAX_AGE_SECONDS + 1

    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))  # dispara el barrido
    assert n8n_live_canvas_sink.health()["active_traces"] == 0


def test_resume_retries_on_a_real_409_and_succeeds_once_n8n_catches_up(monkeypatch):
    """Hallazgo real (2026-08-14): `responseMode: responseNode` puede
    devolver el `execution_id` antes de que la ejecución termine de llegar
    al nodo Wait — el primer resume puede pisar esa ventana y recibir 409
    aunque la ejecución sí exista de verdad."""
    sleeps = []
    monkeypatch.setattr(n8n_live_canvas_sink.time, "sleep", lambda s: sleeps.append(s))
    attempts = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        attempts["n"] += 1
        if attempts["n"] < 3:
            return _FakeResponse(409)
        return _FakeResponse(200)

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))

    assert attempts["n"] == 3
    assert len(sleeps) == 2  # dos reintentos antes de que el tercero funcione
    assert n8n_live_canvas_sink.health()["resumed"] == 1
    assert n8n_live_canvas_sink.health()["failed"] == 0


def test_resume_gives_up_after_the_real_retry_budget_and_counts_it_as_failed(monkeypatch):
    monkeypatch.setattr(n8n_live_canvas_sink.time, "sleep", lambda s: None)

    def fake_post(url, json=None, timeout=None):
        if url == n8n_live_canvas_sink._trigger_url():
            return _FakeResponse(200, body=[{"executionId": "exec-42"}])
        return _FakeResponse(409)  # sigue en conflicto siempre

    monkeypatch.setattr(n8n_live_canvas_sink.requests, "post", fake_post)

    n8n_live_canvas_sink.handle_event(_turn_started(trace_id="trace-1"))
    n8n_live_canvas_sink.handle_event(_some_stage_event(trace_id="trace-1"))

    health = n8n_live_canvas_sink.health()
    assert health["resumed"] == 0
    assert health["failed"] == 1


def test_health_reports_not_configured_by_default():
    assert n8n_live_canvas_sink.health() == {
        "configured": False, "started": 0, "resumed": 0, "failed": 0, "last_error": None, "active_traces": 0,
    }
