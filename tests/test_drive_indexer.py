import json
import time

from snarf.knowledge.drive_indexer import FREE_TIER_DRIVE_QUERY, DriveIndexer
from snarf.knowledge.extraction import ExtractionResult


class FakeDrive:
    def __init__(self, files):
        self._files = files
        self.received_queries = []

    def iter_all_files(self, query=None):
        self.received_queries.append(query)
        yield from self._files


class FakeExtractor:
    def __init__(self, results, delay=0.0):
        self._results = results
        self._delay = delay

    def extract(self, file):
        if self._delay:
            time.sleep(self._delay)
        return self._results[file["id"]]


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def embed(self, texts, input_type="document"):
        self.calls.append((list(texts), input_type))
        return [[float(len(t))] for t in texts]


class FakeVectorStore:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add(self, ids, embeddings, documents, metadatas):
        self.added.append((ids, embeddings, documents, metadatas))

    def delete_by_file_id(self, file_id):
        self.deleted.append(file_id)

    def search(self, query_embedding, top_k=5):
        return [{"text": "resultado", "embedding": query_embedding, "top_k": top_k}]

    def get_by_file_id(self, file_id):
        chunks = []
        for ids, _embeddings, documents, metadatas in self.added:
            for i, meta in enumerate(metadatas):
                if meta.get("file_id") == file_id:
                    chunks.append({"id": ids[i], "text": documents[i], "metadata": meta})
        return chunks


def make_indexer(tmp_path, files, results, delay=0.0, embeddings=None, vector_store=None):
    drive = FakeDrive(files)
    extractor = FakeExtractor(results, delay=delay)
    embeddings = embeddings or FakeEmbeddings()
    vector_store = vector_store or FakeVectorStore()
    indexer = DriveIndexer(drive, extractor, embeddings, vector_store, tmp_path / "manifest.json")
    return indexer, embeddings, vector_store


def wait_until_idle(indexer, timeout=2.0):
    deadline = time.time() + timeout
    while indexer.status()["running"] and time.time() < deadline:
        time.sleep(0.01)


def test_scan_counts_files_and_bytes_by_category_excluding_folders(tmp_path):
    files = [
        {"id": "1", "mimeType": "application/pdf", "size": "100"},
        {"id": "2", "mimeType": "application/vnd.google-apps.folder", "size": "0"},
        {"id": "3", "mimeType": "image/png", "size": "50"},
    ]
    indexer, _, _ = make_indexer(tmp_path, files, {})
    result = indexer.scan()
    assert result["total_files"] == 2
    assert result["total_bytes"] == 150
    assert result["by_category"]["folder"]["count"] == 1
    assert result["by_category"]["pdf"]["count"] == 1


def test_start_processes_files_and_stores_chunks_with_embeddings(tmp_path):
    files = [{"id": "1", "mimeType": "application/pdf", "name": "a.pdf", "modifiedTime": "t1"}]
    results = {"1": ExtractionResult(text="contenido extraído del pdf")}
    indexer, embeddings, vector_store = make_indexer(tmp_path, files, results)

    indexer.start()
    wait_until_idle(indexer)

    status = indexer.status()
    assert status["processed"] == 1
    assert status["indexed"] == 1
    assert len(vector_store.added) == 1
    assert len(embeddings.calls) == 1
    _ids, _embeds, _docs, metadatas = vector_store.added[0]
    assert metadatas[0]["location"] == "drive"


def test_start_marks_unsupported_files_as_skipped_without_storing_anything(tmp_path):
    files = [{"id": "1", "mimeType": "application/zip", "name": "a.zip", "modifiedTime": "t1"}]
    results = {"1": ExtractionResult(skipped_reason="tipo no soportado: application/zip")}
    indexer, _, vector_store = make_indexer(tmp_path, files, results)

    indexer.start()
    wait_until_idle(indexer)

    assert indexer.status()["skipped"] == 1
    assert vector_store.added == []


def test_start_marks_extraction_errors_without_crashing_the_run(tmp_path):
    class BoomExtractor:
        def extract(self, file):
            raise RuntimeError("fallo simulado")

    files = [{"id": "1", "mimeType": "application/pdf", "name": "a.pdf", "modifiedTime": "t1"}]
    indexer = DriveIndexer(FakeDrive(files), BoomExtractor(), FakeEmbeddings(), FakeVectorStore(), tmp_path / "manifest.json")

    indexer.start()
    wait_until_idle(indexer)

    assert indexer.status()["errors"] == 1


def test_second_run_skips_files_whose_modified_time_did_not_change(tmp_path):
    files = [{"id": "1", "mimeType": "application/pdf", "name": "a.pdf", "modifiedTime": "t1"}]
    results = {"1": ExtractionResult(text="contenido")}
    indexer, _, vector_store = make_indexer(tmp_path, files, results)

    indexer.start()
    wait_until_idle(indexer)
    indexer.start()
    wait_until_idle(indexer)

    assert len(vector_store.added) == 1


def test_stop_halts_processing_before_all_files_finish(tmp_path):
    files = [{"id": str(i), "mimeType": "application/pdf", "name": f"{i}.pdf", "modifiedTime": "t1"} for i in range(20)]
    results = {str(i): ExtractionResult(text="contenido") for i in range(20)}
    indexer, _, _ = make_indexer(tmp_path, files, results, delay=0.05)

    indexer.start()
    time.sleep(0.06)
    indexer.stop()
    wait_until_idle(indexer)

    assert indexer.status()["processed"] < 20


def test_starting_while_already_running_reports_already_running(tmp_path):
    files = [{"id": str(i), "mimeType": "application/pdf", "name": f"{i}.pdf", "modifiedTime": "t1"} for i in range(5)]
    results = {str(i): ExtractionResult(text="contenido") for i in range(5)}
    indexer, _, _ = make_indexer(tmp_path, files, results, delay=0.05)

    indexer.start()
    result = indexer.start()
    indexer.stop()
    wait_until_idle(indexer)

    assert result["status"] == "already_running"


def test_search_embeds_the_query_and_delegates_to_the_vector_store(tmp_path):
    indexer, embeddings, _ = make_indexer(tmp_path, [], {})
    results = indexer.search("una pregunta", top_k=3)
    assert embeddings.calls == [(["una pregunta"], "query")]
    assert results[0]["top_k"] == 3


def test_index_file_indexes_a_single_file_immediately_without_a_background_run(tmp_path):
    file = {"id": "1", "mimeType": "application/pdf", "name": "a.pdf", "modifiedTime": "t1"}
    results = {"1": ExtractionResult(text="contenido recién subido")}
    indexer, _, vector_store = make_indexer(tmp_path, [], results)

    result = indexer.index_file(file)

    assert result["status"] == "indexed"
    assert len(vector_store.added) == 1
    assert indexer.status()["running"] is False


def test_get_indexed_text_returns_the_text_stored_for_that_file(tmp_path):
    file = {"id": "1", "mimeType": "image/png", "name": "foto.png", "modifiedTime": "t1"}
    results = {"1": ExtractionResult(text="una descripción real de la imagen")}
    indexer, _, _ = make_indexer(tmp_path, [], results)

    indexer.index_file(file)

    assert indexer.get_indexed_text("1") == "una descripción real de la imagen"


def test_get_indexed_text_is_empty_for_a_file_never_indexed(tmp_path):
    indexer, _, _ = make_indexer(tmp_path, [], {})
    assert indexer.get_indexed_text("no-existe") == ""


def test_index_local_text_stores_chunks_tagged_as_local(tmp_path):
    indexer, embeddings, vector_store = make_indexer(tmp_path, [], {})
    result = indexer.index_local_text("local:abc", "borrador.md", "contenido real de un borrador local")
    assert result["status"] == "indexed"
    assert len(vector_store.added) == 1
    _ids, _embeds, _docs, metadatas = vector_store.added[0]
    assert metadatas[0]["location"] == "local"
    assert metadatas[0]["file_id"] == "local:abc"


def test_index_local_text_merges_extra_metadata(tmp_path):
    indexer, _, vector_store = make_indexer(tmp_path, [], {})
    indexer.index_local_text("local:abc", "borrador.md", "contenido", extra_metadata={"path": "/local/files/borrador.md"})
    _ids, _embeds, _docs, metadatas = vector_store.added[0]
    assert metadatas[0]["path"] == "/local/files/borrador.md"


def test_index_local_text_with_empty_text_is_skipped_without_storing_anything(tmp_path):
    indexer, _, vector_store = make_indexer(tmp_path, [], {})
    result = indexer.index_local_text("local:abc", "vacio.md", "   ")
    assert result["status"] == "skipped_unsupported"
    assert vector_store.added == []


def test_scan_resolves_the_free_tier_alias_to_the_real_drive_query(tmp_path):
    drive = FakeDrive([])
    indexer = DriveIndexer(drive, FakeExtractor({}), FakeEmbeddings(), FakeVectorStore(), tmp_path / "manifest.json")
    indexer.scan(query="free_tier")
    assert drive.received_queries == [FREE_TIER_DRIVE_QUERY]


def test_scan_passes_through_a_custom_query_unchanged(tmp_path):
    drive = FakeDrive([])
    indexer = DriveIndexer(drive, FakeExtractor({}), FakeEmbeddings(), FakeVectorStore(), tmp_path / "manifest.json")
    indexer.scan(query="'folder-id' in parents")
    assert drive.received_queries == ["'folder-id' in parents"]


def test_catalog_unsupported_groups_by_real_mime_type_and_persists_a_registry(tmp_path):
    files = [
        {"id": "1", "name": "robot_trading.ex4", "mimeType": "application/octet-stream", "size": "100"},
        {"id": "2", "name": "otro_robot.ex4", "mimeType": "application/octet-stream", "size": "200"},
        {"id": "3", "name": "backup.rar", "mimeType": "application/vnd.rar", "size": "50"},
        {"id": "4", "name": "no_es_other.pdf", "mimeType": "application/pdf", "size": "999"},
    ]
    indexer = DriveIndexer(FakeDrive(files), FakeExtractor({}), FakeEmbeddings(), FakeVectorStore(), tmp_path / "manifest.json")

    result = indexer.catalog_unsupported()

    assert result["total_files"] == 3
    assert result["by_mime_type"]["application/octet-stream"]["count"] == 2
    assert result["by_mime_type"]["application/octet-stream"]["bytes"] == 300
    assert "robot_trading.ex4" in result["by_mime_type"]["application/octet-stream"]["examples"]
    assert result["by_mime_type"]["application/vnd.rar"]["count"] == 1

    saved = json.loads((tmp_path / "unsupported_catalog.json").read_text(encoding="utf-8"))
    assert len(saved["files"]) == 3
    assert {f["id"] for f in saved["files"]} == {"1", "2", "3"}
