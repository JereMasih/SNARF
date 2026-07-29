from snarf.capabilities.google_retry import retry_once_with_fresh_client


class FakeCapability:
    def __init__(self, fail_times=0):
        self._service = "stale-service"
        self._fail_times = fail_times
        self._calls = 0

    @retry_once_with_fresh_client
    def do_thing(self):
        self._calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("[SSL] record layer failure (_ssl.c:2648)")
        return self._service


def test_retry_once_with_fresh_client_succeeds_after_one_transient_failure():
    """Bug real visto en producción: una conexión de Google cacheada por
    horas en un proceso de larga vida falla con un error SSL transitorio —
    reintentar una vez con el cliente reconstruido resuelve la mayoría."""
    cap = FakeCapability(fail_times=1)
    result = cap.do_thing()
    assert result is None  # _service quedó en None tras el reset, nunca se reconstruyó (eso lo hace _client())
    assert cap._calls == 2


def test_retry_once_with_fresh_client_resets_service_before_retrying():
    cap = FakeCapability(fail_times=1)
    cap.do_thing()
    # El primer fallo debe haber baleado self._service para forzar que
    # _client() lo reconstruya en el próximo uso real (no en este test, que
    # no llama a _client()).
    assert cap._service is None


def test_retry_once_with_fresh_client_propagates_a_persistent_real_failure():
    """No debe ocultar un fallo real y persistente (ej. credenciales
    revocadas) — reintenta una sola vez, después deja que el error suba."""
    cap = FakeCapability(fail_times=99)
    try:
        cap.do_thing()
        assert False, "debería haber propagado la excepción"
    except RuntimeError as exc:
        assert "SSL" in str(exc)
    assert cap._calls == 2  # intento original + un solo reintento, no más


def test_retry_once_with_fresh_client_does_not_retry_when_the_first_call_succeeds():
    cap = FakeCapability(fail_times=0)
    result = cap.do_thing()
    assert result == "stale-service"
    assert cap._calls == 1
