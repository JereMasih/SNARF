from snarf.capabilities.google_drive import GoogleDrive


class FakeFilesResource:
    def __init__(self, pages, media_bytes=None):
        self._pages = pages
        self._media_bytes = media_bytes or {}

    def list(self, **params):
        page_token = params.get("pageToken")
        page = self._pages[page_token or "first"]
        return SimpleExecutable(page)

    def get_media(self, fileId):
        return SimpleExecutable(self._media_bytes[fileId])


class SimpleExecutable:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class FakeService:
    def __init__(self, pages, media_bytes=None):
        self._files = FakeFilesResource(pages, media_bytes)

    def files(self):
        return self._files


def make_drive(pages=None, media_bytes=None):
    drive = GoogleDrive.__new__(GoogleDrive)
    drive._service = FakeService(pages or {}, media_bytes)
    return drive


def test_iter_all_files_follows_pagination_across_multiple_pages():
    pages = {
        "first": {"files": [{"id": "1"}, {"id": "2"}], "nextPageToken": "page2"},
        "page2": {"files": [{"id": "3"}], "nextPageToken": None},
    }
    drive = make_drive(pages)
    files = list(drive.iter_all_files())
    assert [f["id"] for f in files] == ["1", "2", "3"]


def test_iter_all_files_stops_when_there_is_a_single_page():
    pages = {"first": {"files": [{"id": "1"}]}}
    drive = make_drive(pages)
    files = list(drive.iter_all_files())
    assert [f["id"] for f in files] == ["1"]


def test_read_file_bytes_returns_raw_bytes_without_decoding():
    drive = make_drive(media_bytes={"f1": b"\xff\xd8binary-image-bytes"})
    assert drive.read_file_bytes("f1") == b"\xff\xd8binary-image-bytes"
