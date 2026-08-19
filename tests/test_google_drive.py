from snarf.capabilities.google_drive import GoogleDrive


class FakeFilesResource:
    def __init__(self, pages, media_bytes=None, create_response=None, update_response=None):
        self._pages = pages
        self._media_bytes = media_bytes or {}
        self._create_response = create_response
        self._update_response = update_response
        self.create_calls = []
        self.update_calls = []
        self.list_calls = []

    def list(self, **params):
        self.list_calls.append(params)
        page_token = params.get("pageToken")
        page = self._pages[page_token or "first"]
        return SimpleExecutable(page)

    def get_media(self, fileId):
        return SimpleExecutable(self._media_bytes[fileId])

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleExecutable(self._create_response)

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        return SimpleExecutable(self._update_response)


class FakePermissionsResource:
    def __init__(self, create_response=None):
        self._create_response = create_response
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleExecutable(self._create_response)


class SimpleExecutable:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class FakeService:
    def __init__(self, pages, media_bytes=None, create_response=None, update_response=None, permission_response=None):
        self._files = FakeFilesResource(pages, media_bytes, create_response, update_response)
        self._permissions = FakePermissionsResource(permission_response)

    def files(self):
        return self._files

    def permissions(self):
        return self._permissions


def make_drive(pages=None, media_bytes=None, create_response=None, update_response=None, permission_response=None):
    drive = GoogleDrive.__new__(GoogleDrive)
    drive._service = FakeService(pages or {}, media_bytes, create_response, update_response, permission_response)
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


def test_list_files_sends_free_text_query_normalized_to_real_drive_syntax():
    # Regresión real de producción: pasar texto libre tal cual como `q`
    # rompía la API de Drive con un 400 ("Invalid Value") — ver ADR de esta
    # ronda / snarf/capabilities/google_drive.py::normalize_drive_query.
    pages = {"first": {"files": []}}
    drive = make_drive(pages)
    drive.list_files(query="vida es sueño")
    assert drive._service._files.list_calls[0]["q"] == "fullText contains 'vida es sueño'"


def test_list_files_sends_real_drive_syntax_unchanged():
    pages = {"first": {"files": []}}
    drive = make_drive(pages)
    drive.list_files(query="name contains 'informe'")
    assert drive._service._files.list_calls[0]["q"] == "name contains 'informe'"


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


def test_rename_file_sends_the_new_name_in_the_update_body():
    drive = make_drive(update_response={"id": "f1", "name": "Archivos"})
    result = drive.rename_file("f1", "Archivos")
    assert result["name"] == "Archivos"
    call = drive._service._files.update_calls[0]
    assert call["fileId"] == "f1"
    assert call["body"] == {"name": "Archivos"}


def test_share_file_with_email_creates_a_user_permission():
    drive = make_drive(permission_response={"id": "p1", "type": "user", "role": "reader"})
    drive.share_file("f1", role="reader", email="alguien@example.com")
    call = drive._service._permissions.create_calls[0]
    assert call["fileId"] == "f1"
    assert call["body"] == {"type": "user", "role": "reader", "emailAddress": "alguien@example.com"}


def test_share_file_without_email_creates_an_anyone_permission():
    drive = make_drive(permission_response={"id": "p2", "type": "anyone", "role": "reader"})
    drive.share_file("f1", role="reader")
    call = drive._service._permissions.create_calls[0]
    assert call["body"] == {"type": "anyone", "role": "reader"}


class FakeDocsDocumentsResource:
    def __init__(self, get_response):
        self._get_response = get_response
        self.batch_update_calls = []

    def get(self, documentId):
        return SimpleExecutable(self._get_response)

    def batchUpdate(self, documentId, body):
        self.batch_update_calls.append({"documentId": documentId, "body": body})
        return SimpleExecutable({})


class FakeDocsService:
    def __init__(self, get_response):
        self._documents = FakeDocsDocumentsResource(get_response)

    def documents(self):
        return self._documents


def make_drive_with_docs(get_response):
    drive = GoogleDrive.__new__(GoogleDrive)
    docs_service = FakeDocsService(get_response)
    drive._docs_client = lambda: docs_service
    return drive, docs_service


def test_read_document_text_joins_every_paragraph_text_run():
    doc = {
        "body": {
            "content": [
                {"paragraph": {"elements": [{"textRun": {"content": "Hola "}}, {"textRun": {"content": "mundo\n"}}]}},
                {"paragraph": {"elements": [{"textRun": {"content": "segunda línea\n"}}]}},
            ]
        }
    }
    drive, _ = make_drive_with_docs(doc)
    assert drive.read_document_text("doc-1") == "Hola mundo\nsegunda línea\n"


def test_replace_document_body_deletes_existing_content_then_inserts_new_text():
    doc = {"body": {"content": [{"endIndex": 25}]}}
    drive, docs_service = make_drive_with_docs(doc)
    result = drive.replace_document_body("doc-1", "texto nuevo")
    call = docs_service._documents.batch_update_calls[0]
    assert call["documentId"] == "doc-1"
    requests = call["body"]["requests"]
    assert requests[0] == {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": 24}}}
    assert requests[1] == {"insertText": {"location": {"index": 1}, "text": "texto nuevo"}}
    assert result == {"documentId": "doc-1", "status": "updated"}


def test_replace_document_body_skips_delete_when_document_is_already_empty():
    doc = {"body": {"content": [{"endIndex": 1}]}}
    drive, docs_service = make_drive_with_docs(doc)
    drive.replace_document_body("doc-1", "primer contenido")
    requests = docs_service._documents.batch_update_calls[0]["body"]["requests"]
    assert requests == [{"insertText": {"location": {"index": 1}, "text": "primer contenido"}}]


class RaisingExecutable:
    def __init__(self, exc):
        self._exc = exc

    def execute(self):
        raise self._exc


def _service_disabled_http_error(project="516998840048"):
    """Mismo shape real que devuelve Google cuando la API de Docs está
    deshabilitada en el proyecto (ver activity_log.jsonl, bug real de
    producción del 2026-08-19) — reason SERVICE_DISABLED y una
    activationUrl real adentro del mensaje."""
    import json
    from types import SimpleNamespace

    from googleapiclient.errors import HttpError

    url = f"https://console.developers.google.com/apis/api/docs.googleapis.com/overview?project={project}"
    message = (
        f"Google Docs API has not been used in project {project} before or it is disabled. "
        f"Enable it by visiting {url} then retry."
    )
    content = json.dumps(
        {"error": {"message": message, "status": "PERMISSION_DENIED", "details": [{"reason": "SERVICE_DISABLED"}]}}
    ).encode("utf-8")
    return HttpError(SimpleNamespace(status=403, reason="Forbidden"), content, uri="https://docs.googleapis.com/v1/documents/doc-1")


def test_read_document_text_raises_a_clean_error_when_docs_api_is_disabled():
    import pytest

    drive = GoogleDrive.__new__(GoogleDrive)
    docs_service = FakeDocsService(None)
    docs_service._documents.get = lambda documentId: RaisingExecutable(_service_disabled_http_error())
    drive._docs_client = lambda: docs_service

    with pytest.raises(RuntimeError) as exc_info:
        drive.read_document_text("doc-1")
    assert "deshabilitada" in str(exc_info.value)
    assert "console.developers.google.com/apis/api/docs.googleapis.com" in str(exc_info.value)


def test_replace_document_body_raises_a_clean_error_when_docs_api_is_disabled():
    import pytest

    drive = GoogleDrive.__new__(GoogleDrive)
    docs_service = FakeDocsService(None)
    docs_service._documents.get = lambda documentId: RaisingExecutable(_service_disabled_http_error())
    drive._docs_client = lambda: docs_service

    with pytest.raises(RuntimeError) as exc_info:
        drive.replace_document_body("doc-1", "texto nuevo")
    assert "deshabilitada" in str(exc_info.value)


def test_read_document_text_lets_unrelated_http_errors_through_unchanged():
    import json
    import pytest
    from types import SimpleNamespace

    from googleapiclient.errors import HttpError

    content = json.dumps({"error": {"message": "Document not found"}}).encode("utf-8")
    not_found = HttpError(SimpleNamespace(status=404, reason="Not Found"), content, uri="u")

    drive = GoogleDrive.__new__(GoogleDrive)
    docs_service = FakeDocsService(None)
    docs_service._documents.get = lambda documentId: RaisingExecutable(not_found)
    drive._docs_client = lambda: docs_service

    with pytest.raises(HttpError):
        drive.read_document_text("doc-1")
