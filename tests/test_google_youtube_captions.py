from googleapiclient.errors import HttpError

from snarf.capabilities.google_youtube import GoogleYouTube


class SimpleExecutable:
    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error

    def execute(self):
        if self._error:
            raise self._error
        return self._value


class FakeCaptionsResource:
    def __init__(self, list_response, download_response=None, download_error=None):
        self._list_response = list_response
        self._download_response = download_response
        self._download_error = download_error
        self.download_calls = []

    def list(self, part, videoId):
        return SimpleExecutable(self._list_response)

    def download(self, id, tfmt):
        self.download_calls.append((id, tfmt))
        return SimpleExecutable(self._download_response, self._download_error)


class FakeService:
    def __init__(self, captions_resource):
        self._captions_resource = captions_resource

    def captions(self):
        return self._captions_resource


def _fake_http_error():
    class _FakeResp:
        status = 403
        reason = "Forbidden"

    return HttpError(_FakeResp(), b'{"error": "forbidden"}')


def make_youtube(captions_resource):
    yt = GoogleYouTube.__new__(GoogleYouTube)
    yt._service = FakeService(captions_resource)
    return yt


def test_get_video_captions_returns_none_when_no_track_exists():
    resource = FakeCaptionsResource(list_response={"items": []})
    yt = make_youtube(resource)
    assert yt.get_video_captions("v1") is None


def test_get_video_captions_returns_the_real_transcript_text():
    resource = FakeCaptionsResource(
        list_response={"items": [{"id": "cap-1"}]}, download_response=b"1\n00:00:00,000 --> 00:00:02,000\nHola mundo\n"
    )
    yt = make_youtube(resource)
    result = yt.get_video_captions("v1")
    assert "Hola mundo" in result
    assert resource.download_calls == [("cap-1", "srt")]


def test_get_video_captions_returns_none_on_a_real_http_error_not_owned():
    # Caso real y esperado: el video no es del fundador, la API rechaza la
    # descarga con un 403 — se trata igual que "no hay captions", nunca
    # revienta el flujo de research.
    resource = FakeCaptionsResource(list_response={"items": [{"id": "cap-1"}]}, download_error=_fake_http_error())
    yt = make_youtube(resource)
    assert yt.get_video_captions("v1") is None
