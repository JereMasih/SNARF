from snarf.knowledge.document_publisher import DocumentPublisher


class FakeBuilder:
    def build_markdown(self, title, content):
        return f"# {title}\n\n{content}".encode("utf-8")

    def build_pdf(self, title, content):
        return b"pdf-bytes"

    def build_pptx(self, title, slides):
        return b"pptx-bytes"

    def build_xlsx(self, title, rows):
        return b"xlsx-bytes"


class FakeDrive:
    def __init__(self):
        self.folder_calls = []
        self.upload_calls = []

    def get_or_create_folder(self, name, parent_id=None):
        self.folder_calls.append(name)
        return "folder-id"

    def upload_file(self, name, content, mime_type, parent_id=None, convert_to=None):
        self.upload_calls.append(
            {"name": name, "content": content, "mime_type": mime_type, "parent_id": parent_id, "convert_to": convert_to}
        )
        return {"id": "file-1", "name": name, "mimeType": convert_to or mime_type, "modifiedTime": "t1", "webViewLink": "http://drive/file-1"}


class FakeIndexer:
    def __init__(self, should_fail=False):
        self.indexed_files = []
        self.local_index_calls = []
        self.should_fail = should_fail

    def index_file(self, file):
        if self.should_fail:
            raise RuntimeError("fallo simulado")
        self.indexed_files.append(file["id"])
        return {"status": "indexed", "chunk_count": 1}

    def index_local_text(self, item_id, name, text, extra_metadata=None):
        self.local_index_calls.append({"id": item_id, "name": name, "text": text, "extra_metadata": extra_metadata})
        return {"status": "indexed", "chunk_count": 1}


class FakeLocalStore:
    def __init__(self):
        self.saved = []

    def save(self, name, content):
        self.saved.append({"name": name, "content": content})
        return f"/local/files/{name}"


def make_publisher(indexer=None, local_store=None, user_id="fundador", allow_server_storage=True):
    return DocumentPublisher(
        FakeBuilder(),
        FakeDrive(),
        indexer or FakeIndexer(),
        local_store or FakeLocalStore(),
        user_id=user_id,
        allow_server_storage=allow_server_storage,
    )


def test_create_document_uploads_to_the_snarf_folder_and_indexes_it():
    publisher = make_publisher()
    result = publisher.create_document("Mi Reporte", "contenido", format="pdf")
    assert result["id"] == "file-1"
    assert result["indexed"] is True
    assert result["location"] == "drive"
    assert publisher._drive.folder_calls == ["Snarf - Archivos"]
    assert publisher._drive.upload_calls[0]["mime_type"] == "application/pdf"


def test_create_document_google_doc_uploads_plain_text_and_requests_conversion():
    publisher = make_publisher()
    publisher.create_document("Titulo", "contenido plano", format="google_doc")
    call = publisher._drive.upload_calls[0]
    assert call["mime_type"] == "text/plain"
    assert call["convert_to"] == "application/vnd.google-apps.document"
    assert call["content"] == b"contenido plano"


def test_create_document_rejects_an_unsupported_format():
    publisher = make_publisher()
    try:
        publisher.create_document("T", "c", format="xlsx")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass


def test_create_spreadsheet_uploads_xlsx():
    publisher = make_publisher()
    result = publisher.create_spreadsheet("Gastos", [["a", "b"]], format="xlsx")
    assert result["id"] == "file-1"
    assert publisher._drive.upload_calls[0]["mime_type"].endswith("spreadsheetml.sheet")


def test_create_spreadsheet_google_sheet_requests_conversion():
    publisher = make_publisher()
    publisher.create_spreadsheet("Gastos", [["a"]], format="google_sheet")
    assert publisher._drive.upload_calls[0]["convert_to"] == "application/vnd.google-apps.spreadsheet"


def test_create_spreadsheet_rejects_an_unsupported_format():
    publisher = make_publisher()
    try:
        publisher.create_spreadsheet("T", [["a"]], format="pdf")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass


def test_create_presentation_uploads_pptx():
    publisher = make_publisher()
    result = publisher.create_presentation("Charla", [{"title": "s1", "body": "b1"}], format="pptx")
    assert result["id"] == "file-1"


def test_create_presentation_google_slide_requests_conversion():
    publisher = make_publisher()
    publisher.create_presentation("Charla", [], format="google_slide")
    assert publisher._drive.upload_calls[0]["convert_to"] == "application/vnd.google-apps.presentation"


def test_create_presentation_rejects_an_unsupported_format():
    publisher = make_publisher()
    try:
        publisher.create_presentation("T", [], format="markdown")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass


def test_folder_is_resolved_only_once_across_multiple_creations():
    publisher = make_publisher()
    publisher.create_document("A", "x", format="markdown")
    publisher.create_document("B", "y", format="markdown")
    assert publisher._drive.folder_calls == ["Snarf - Archivos"]


def test_creation_result_reports_not_indexed_when_indexing_fails_but_the_file_still_exists():
    publisher = make_publisher(indexer=FakeIndexer(should_fail=True))
    result = publisher.create_document("T", "c", format="markdown")
    assert result["indexed"] is False
    assert result["id"] == "file-1"


def test_create_document_device_never_touches_drive():
    publisher = make_publisher()
    result = publisher.create_document("Borrador", "contenido local", format="markdown", destination="device")
    assert result["location"] == "device"
    assert result["webViewLink"] is None
    assert publisher._drive.upload_calls == []
    assert publisher._drive.folder_calls == []
    assert publisher._local_store.saved[0]["name"] == "Borrador.md"


def test_create_document_device_returns_a_download_url():
    publisher = make_publisher(user_id="fundador")
    result = publisher.create_document("Borrador", "contenido", format="markdown", destination="device")
    assert result["download_url"] == "/files/local/fundador/Borrador.md"


def test_create_document_device_indexes_the_source_text_directly():
    indexer = FakeIndexer()
    publisher = make_publisher(indexer=indexer)
    publisher.create_document("Borrador", "el texto real a indexar", format="markdown", destination="device")
    assert indexer.local_index_calls[0]["text"] == "el texto real a indexar"
    assert indexer.local_index_calls[0]["id"].startswith("device:")
    assert indexer.local_index_calls[0]["extra_metadata"]["location"] == "device"


def test_create_document_device_rejects_google_native_formats():
    publisher = make_publisher()
    try:
        publisher.create_document("T", "c", format="google_doc", destination="device")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass


def test_create_spreadsheet_device_indexes_a_flattened_text_of_the_rows():
    indexer = FakeIndexer()
    publisher = make_publisher(indexer=indexer)
    publisher.create_spreadsheet("Gastos", [["item", "monto"], ["café", 5]], format="xlsx", destination="device")
    assert "item" in indexer.local_index_calls[0]["text"]
    assert "café" in indexer.local_index_calls[0]["text"]


def test_create_presentation_device_indexes_a_flattened_text_of_the_slides():
    indexer = FakeIndexer()
    publisher = make_publisher(indexer=indexer)
    publisher.create_presentation("Charla", [{"title": "s1", "body": "contenido real"}], format="pptx", destination="device")
    assert "contenido real" in indexer.local_index_calls[0]["text"]


def test_create_document_server_is_allowed_for_the_founder():
    publisher = make_publisher(allow_server_storage=True)
    result = publisher.create_document("Nota interna", "contenido", format="markdown", destination="server")
    assert result["location"] == "server"
    assert "download_url" not in result


def test_create_document_server_is_rejected_for_anyone_else():
    publisher = make_publisher(user_id="otro_usuario", allow_server_storage=False)
    try:
        publisher.create_document("T", "c", format="markdown", destination="server")
        assert False, "debería haber lanzado ValueError"
    except ValueError:
        pass
    assert publisher._local_store.saved == []
