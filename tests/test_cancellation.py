from snarf.telemetry import cancellation


def test_is_cancelled_false_for_unknown_id():
    assert cancellation.is_cancelled("nunca-registrado") is False


def test_is_cancelled_false_for_none():
    assert cancellation.is_cancelled(None) is False


def test_cancel_unregistered_id_returns_false():
    assert cancellation.cancel("nunca-registrado") is False


def test_register_then_cancel_marks_it_cancelled():
    cancellation.register("req-1")
    try:
        assert cancellation.cancel("req-1") is True
        assert cancellation.is_cancelled("req-1") is True
    finally:
        cancellation.finish("req-1")


def test_double_cancel_is_idempotent():
    cancellation.register("req-2")
    try:
        assert cancellation.cancel("req-2") is True
        assert cancellation.cancel("req-2") is True
        assert cancellation.is_cancelled("req-2") is True
    finally:
        cancellation.finish("req-2")


def test_finish_clears_active_and_cancelled_state():
    cancellation.register("req-3")
    cancellation.cancel("req-3")
    cancellation.finish("req-3")
    assert cancellation.is_cancelled("req-3") is False
    # Terminado el ciclo de vida, un cancel tardío (carrera real con /cancel
    # llegando después de que la respuesta ya se persistió) no debe fingir éxito.
    assert cancellation.cancel("req-3") is False
