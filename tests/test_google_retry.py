from snarf.capabilities import google_retry
from snarf.capabilities.google_retry import retry_with_fresh_client


class FakeCapability:
    def __init__(self, fail_times=0):
        self._service = "stale-service"
        self._fail_times = fail_times
        self._calls = 0

    @retry_with_fresh_client
    def do_thing(self):
        self._calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("[SSL] record layer failure (_ssl.c:2648)")
        return self._service


def test_retry_with_fresh_client_succeeds_after_transient_failures_within_max_attempts(monkeypatch):
    monkeypatch.setattr(google_retry, "RETRY_DELAY_SECONDS", 0)
    # Confirmado en vivo: un solo reintento no alcanza siempre (la falla SSL
    # puede pegarle también al reintento) — con 2 fallos seguidos, todavía
    # queda un tercer intento real dentro de MAX_ATTEMPTS.
    cap = FakeCapability(fail_times=2)
    result = cap.do_thing()
    assert result is None  # _service quedó en None tras el último reset, nunca se reconstruyó (eso lo hace _client())
    assert cap._calls == 3


def test_retry_with_fresh_client_resets_service_before_each_retry(monkeypatch):
    monkeypatch.setattr(google_retry, "RETRY_DELAY_SECONDS", 0)
    cap = FakeCapability(fail_times=1)
    cap.do_thing()
    assert cap._service is None


def test_retry_with_fresh_client_propagates_a_persistent_real_failure(monkeypatch):
    """No debe ocultar un fallo real y persistente (ej. credenciales
    revocadas) — agota MAX_ATTEMPTS intentos, después deja que el error suba."""
    monkeypatch.setattr(google_retry, "RETRY_DELAY_SECONDS", 0)
    cap = FakeCapability(fail_times=99)
    try:
        cap.do_thing()
        assert False, "debería haber propagado la excepción"
    except RuntimeError as exc:
        assert "SSL" in str(exc)
    assert cap._calls == google_retry.MAX_ATTEMPTS


def test_retry_with_fresh_client_does_not_retry_when_the_first_call_succeeds():
    cap = FakeCapability(fail_times=0)
    result = cap.do_thing()
    assert result == "stale-service"
    assert cap._calls == 1
