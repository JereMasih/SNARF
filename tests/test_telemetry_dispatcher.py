import threading
import time

from snarf.telemetry import dispatcher


def test_sync_subscriber_gets_event_inline():
    received = []
    dispatcher.subscribe("s1", received.append, mode=dispatcher.SYNC)
    dispatcher.publish({"event_type": "tool.finished"})
    assert received == [{"event_type": "tool.finished"}]


def test_async_subscriber_gets_event_after_drain():
    received = []
    dispatcher.subscribe("a1", received.append, mode=dispatcher.ASYNC)
    dispatcher.publish({"event_type": "tool.finished"})
    dispatcher.drain(timeout=2.0)
    assert received == [{"event_type": "tool.finished"}]


def test_raising_subscriber_never_propagates_and_is_counted():
    def _boom(event):
        raise RuntimeError("subscriber roto")

    second_received = []
    dispatcher.subscribe("boom", _boom, mode=dispatcher.SYNC)
    dispatcher.subscribe("second", second_received.append, mode=dispatcher.SYNC)

    dispatcher.publish({"event_type": "tool.finished"})  # no debe levantar

    assert second_received == [{"event_type": "tool.finished"}]
    stats = dispatcher.stats()
    assert stats["by_subscriber"]["boom"]["errors"] == 1
    assert "RuntimeError" in stats["by_subscriber"]["boom"]["last_error"]


def test_event_types_filter_delivers_only_matching_types():
    received = []
    dispatcher.subscribe("filtered", received.append, mode=dispatcher.SYNC, event_types={"llm.finished"})
    dispatcher.publish({"event_type": "tool.finished"})
    dispatcher.publish({"event_type": "llm.finished"})
    assert received == [{"event_type": "llm.finished"}]


def test_queue_full_drops_new_event_without_raising():
    slow_gate = threading.Event()

    def _slow(event):
        slow_gate.wait(timeout=2.0)

    dispatcher.subscribe("slow", _slow, mode=dispatcher.ASYNC)
    original_max = dispatcher.MAX_QUEUE
    # El worker/la cola se reusan entre tests (ver dispatcher.reset()) —
    # bajar MAX_QUEUE no alcanza si ya existe una cola vieja con el tamaño
    # default; stop() fuerza que _ensure_worker() cree una nueva con el
    # tamaño chico de este test.
    dispatcher.stop(timeout=1.0)
    dispatcher.MAX_QUEUE = 1
    try:
        # El primer publish() dispara _ensure_worker() con la cola nueva (ya
        # con maxsize=1) y el worker se la come casi de inmediato porque
        # _slow todavía no bloqueó nada — para forzar un descarte real hace
        # falta que el worker esté OCUPADO cuando llegan los siguientes.
        dispatcher.publish({"event_type": "tool.finished", "seq": 0})
        time.sleep(0.05)  # deja que el worker entre a _slow y quede bloqueado
        dispatcher.publish({"event_type": "tool.finished", "seq": 1})
        dispatcher.publish({"event_type": "tool.finished", "seq": 2})  # esta se descarta
        stats_before_release = dispatcher.stats()
    finally:
        slow_gate.set()
        dispatcher.drain(timeout=2.0)
        dispatcher.MAX_QUEUE = original_max
    assert stats_before_release["dropped"] >= 1


def test_concurrent_publish_from_multiple_threads_all_delivered():
    received = []
    lock = threading.Lock()

    def _collect(event):
        with lock:
            received.append(event)

    dispatcher.subscribe("collector", _collect, mode=dispatcher.SYNC)

    def _publish(n):
        dispatcher.publish({"event_type": "tool.finished", "seq": n})

    threads = [threading.Thread(target=_publish, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(received) == 8
    assert {e["seq"] for e in received} == set(range(8))


def test_unsubscribe_stops_delivery():
    received = []
    dispatcher.subscribe("temp", received.append, mode=dispatcher.SYNC)
    assert dispatcher.unsubscribe("temp") is True
    dispatcher.publish({"event_type": "tool.finished"})
    assert received == []
    assert dispatcher.unsubscribe("temp") is False


def test_reset_clears_subscribers_and_stats():
    dispatcher.subscribe("s1", lambda e: None, mode=dispatcher.SYNC)
    dispatcher.publish({"event_type": "tool.finished"})
    dispatcher.reset()
    assert dispatcher.subscribers() == ()
    assert dispatcher.stats() == {"published": 0, "dropped": 0, "by_subscriber": {}}
