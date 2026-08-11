from snarf.telemetry import event_buffer


def test_since_none_returns_everything_buffered():
    event_buffer._append({"event_type": "tool.finished", "seq": "a"})
    event_buffer._append({"event_type": "tool.finished", "seq": "b"})
    rows = event_buffer.since(None)
    assert [e["seq"] for _, e in rows] == ["a", "b"]


def test_since_a_cursor_returns_only_newer_events():
    event_buffer._append({"event_type": "tool.finished", "seq": "a"})
    first_seq = event_buffer.latest_seq()
    event_buffer._append({"event_type": "tool.finished", "seq": "b"})
    event_buffer._append({"event_type": "tool.finished", "seq": "c"})
    rows = event_buffer.since(first_seq)
    assert [e["seq"] for _, e in rows] == ["b", "c"]


def test_since_is_fifo_in_order_of_arrival():
    for i in range(5):
        event_buffer._append({"event_type": "tool.finished", "seq": i})
    rows = event_buffer.since(None)
    assert [e["seq"] for _, e in rows] == [0, 1, 2, 3, 4]


def test_buffer_is_bounded_to_max_events(monkeypatch):
    monkeypatch.setattr(event_buffer, "MAX_EVENTS", 3)
    monkeypatch.setattr(event_buffer, "_buffer", __import__("collections").deque(maxlen=3))
    for i in range(5):
        event_buffer._append({"event_type": "tool.finished", "seq": i})
    rows = event_buffer.since(None)
    assert [e["seq"] for _, e in rows] == [2, 3, 4]


def test_latest_seq_is_none_when_empty():
    assert event_buffer.latest_seq() is None


def test_reset_clears_the_buffer_and_the_cursor():
    event_buffer._append({"event_type": "tool.finished"})
    event_buffer.reset()
    assert event_buffer.since(None) == []
    assert event_buffer.latest_seq() is None
    event_buffer._append({"event_type": "tool.finished", "seq": "after-reset"})
    # El cursor arranca de nuevo desde 1, no sigue creciendo desde antes.
    seq, _ = event_buffer.since(None)[0]
    assert seq == 1


def test_install_subscribes_to_the_dispatcher():
    from snarf.telemetry import dispatcher

    event_buffer.install()
    dispatcher.publish({"event_type": "tool.finished", "seq": "via-dispatcher"})
    dispatcher.drain(timeout=2.0)
    rows = event_buffer.since(None)
    assert [e["seq"] for _, e in rows] == ["via-dispatcher"]
