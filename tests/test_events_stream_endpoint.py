import asyncio

import pytest

import app as app_module
from snarf.telemetry import event_buffer, redis_sink


class _FakeHeaders:
    def __init__(self, values: dict | None = None):
        self._values = {k.lower(): v for k, v in (values or {}).items()}

    def get(self, key, default=None):
        return self._values.get(key.lower(), default)


class _FakeRequest:
    """Duck-types lo mínimo que _events_stream necesita de un Request real
    (.headers.get, is_disconnected async) — evita depender de un TestClient
    real streaming, que para un generador sin fin sería frágil de cortar
    limpio en un test."""

    def __init__(self, headers: dict | None = None, disconnect_after: int = 1):
        self.headers = _FakeHeaders(headers)
        self._checks = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._checks += 1
        return self._checks > self._disconnect_after


async def _collect(agen, limit: int) -> list[str]:
    frames = []
    async for frame in agen:
        frames.append(frame)
        if len(frames) >= limit:
            break
    return frames


def test_stream_from_buffer_yields_a_real_event_as_an_sse_frame():
    event_buffer._append({"event_type": "tool.finished", "skill": "drive_list_files"})
    request = _FakeRequest(disconnect_after=5)
    frames = asyncio.run(_collect(app_module._events_stream(request, None), limit=1))
    assert len(frames) == 1
    frame = frames[0]
    assert frame.startswith("id: 1\n")
    assert "event: tool.finished\n" in frame
    assert '"skill": "drive_list_files"' in frame


def test_stream_from_buffer_respects_an_explicit_cursor():
    event_buffer._append({"event_type": "tool.finished", "skill": "old"})
    first_seq = event_buffer.latest_seq()
    event_buffer._append({"event_type": "tool.finished", "skill": "new"})
    request = _FakeRequest(disconnect_after=5)
    frames = asyncio.run(_collect(app_module._events_stream(request, str(first_seq)), limit=1))
    assert "new" in frames[0]
    assert "old" not in frames[0]


def test_stream_from_buffer_stops_when_the_request_disconnects():
    request = _FakeRequest(disconnect_after=0)

    async def _run():
        frames = []
        async for frame in app_module._events_stream(request, None):
            frames.append(frame)
        return frames

    frames = asyncio.run(_run())
    assert frames == []


def test_stream_uses_the_last_event_id_header_as_the_cursor():
    event_buffer._append({"event_type": "tool.finished", "skill": "old"})
    first_seq = event_buffer.latest_seq()
    event_buffer._append({"event_type": "tool.finished", "skill": "new"})
    request = _FakeRequest(headers={"Last-Event-ID": str(first_seq)}, disconnect_after=5)
    cursor = request.headers.get("last-event-id") or None
    frames = asyncio.run(_collect(app_module._events_stream(request, cursor), limit=1))
    assert "new" in frames[0]


def test_endpoint_requires_authentication(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    with TestClient(app_module.app, base_url="https://testserver") as client:
        res = client.get("/events/stream")
    assert res.status_code == 401
