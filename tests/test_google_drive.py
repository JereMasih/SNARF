from snarf.capabilities.google_drive import GoogleDrive


class FakeFilesResource:
    def __init__(self, pages, media_bytes=None, create_response=None):
        self._pages = pages
        self._media_bytes = media_bytes or {}
        self._create_response = create_response
        self.create_calls = []

    def list(self, **params):
        page_token = params.get("pageToken")
        page = self._pages[page_token or "first"]
        return SimpleExecutable(page)

    def get_media(self, fileId):
        return SimpleExecutable(self._media_bytes[fileId])

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleExecutable(self._create_response)


class SimpleExecutable:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class FakeService:
    def __init__(self, pages, media_bytes=None, create_response=None):
        self._files = FakeFilesResource(pages, media_bytes, create_response)

    def files(self):
        return self._files


def make_drive(pages=None, media_bytes=None, create_response=None):
    drive = GoogleDrive.__new__(GoogleDrive)
    drive._service = FakeService(pages or {}, media_bytes, create_response)
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


def test_get_or_create_folder_returns_existing_id_when_found():
    pages = {"first": {"files": [{"id": "folder-1", "name": "Snarf - Archivos"}]}}
    drive = make_drive(pages)
    assert drive.get_or_create_folder("Snarf - Archivos") == "folder-1"


def test_get_or_create_folder_creates_one_when_not_found():
    pages = {"first": {"files": []}}
    drive = make_drive(pages, create_response={"id": "new-folder", "name": "Snarf - Archivos"})
    assert drive.get_or_create_folder("Snarf - Archivos") == "new-folder"


def test_upload_file_uses_convert_to_as_the_target_mime_type_and_sets_parent():
    drive = make_drive(
        create_response={
            "id": "f1",
            "name": "doc",
            "mimeType": "application/vnd.google-apps.document",
            "webViewLink": "http://x",
        }
    )
    result = drive.upload_file(
        "doc", b"contenido", "text/plain", parent_id="folder-1", convert_to="application/vnd.google-apps.document"
    )
    assert result["id"] == "f1"
    sent_body = drive._service._files.create_calls[0]["body"]
    assert sent_body["mimeType"] == "application/vnd.google-apps.document"
    assert sent_body["parents"] == ["folder-1"]


def test_upload_file_without_convert_to_uses_the_content_mime_type():
    drive = make_drive(create_response={"id": "f2", "name": "a.pdf"})
    drive.upload_file("a.pdf", b"contenido", "application/pdf")
    sent_body = drive._service._files.create_calls[0]["body"]
    assert sent_body["mimeType"] == "application/pdf"
    assert "parents" not in sent_body
