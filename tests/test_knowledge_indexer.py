import time

from snarf.knowledge.indexer import KnowledgeIndexer
from snarf.knowledge.manifest import STATUS_ERROR, STATUS_INDEXED, STATUS_SKIPPED_UNSUPPORTED, IndexManifest
from snarf.knowledge.source import KnowledgeItem


class FakeSource:
    domain = "code"

    def __init__(self, items, texts, delay=0.0):
        self._items = items
        self._texts = texts
        self._delay = delay

    def iter_items(self):
        yield from self._items

    def read_item(self, item):
        if self._delay:
            time.sleep(self._delay)
        text = self._texts[item.id]
        if isinstance(text, Exception):
            raise text
        return text


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
        self.search_calls = []

    def add(self, ids, embeddings, documents, metadatas):
        self.added.append((ids, embeddings, documents, metadatas))

    def delete_by_file_id(self, file_id):
        self.deleted.append(file_id)

    def search(self, query_embedding, top_k=5, where=None):
        self.search_calls.append({"top_k": top_k, "where": where})
        return [{"text": "resultado", "embedding": query_embedding, "top_k": top_k}]


def make_indexer(tmp_path, items, texts, delay=0.0):
    source = FakeSource(items, texts, delay=delay)
    embeddings = FakeEmbeddings()
    vector_store = FakeVectorStore()
    indexer = KnowledgeIndexer(source, embeddings, vector_store, tmp_path / "manifest.json")
    return indexer, embeddings, vector_store


def wait_until_idle(indexer, timeout=2.0):
    deadline = time.time() + timeout
    while indexer.status()["running"] and time.time() < deadline:
        time.sleep(0.01)


def _item(item_id, name="a.py", marker="t1", extra=None):
    return KnowledgeItem(id=item_id, name=name, mime_type="text/x-python", modified_marker=marker, extra_metadata=extra or {})


def test_start_processes_items_and_stores_chunks_with_embeddings(tmp_path):
    items = [_item("1")]
    indexer, embeddings, vector_store = make_indexer(tmp_path, items, {"1": "contenido real de código"})

    indexer.start()
    wait_until_idle(indexer)

    status = indexer.status()
    assert status["processed"] == 1
    assert status["indexed"] == 1
    assert len(vector_store.added) == 1
    assert len(embeddings.calls) == 1
    _ids, _embeds, _docs, metadatas = vector_store.added[0]
    assert metadatas[0]["domain"] == "code"
    assert metadatas[0]["file_id"] == "1"


def test_start_marks_items_with_no_real_text_as_skipped(tmp_path):
    items = [_item("1")]
    indexer, _, vector_store = make_indexer(tmp_path, items, {"1": "   "})

    indexer.start()
    wait_until_idle(indexer)

    assert indexer.status()["skipped"] == 1
    assert vector_store.added == []


def test_start_marks_read_errors_without_crashing_the_run(tmp_path):
    items = [_item("1")]
    indexer, _, _ = make_indexer(tmp_path, items, {"1": RuntimeError("fallo simulado")})

    indexer.start()
    wait_until_idle(indexer)

    assert indexer.status()["errors"] == 1


def test_second_run_skips_items_whose_marker_did_not_change(tmp_path):
    items = [_item("1")]
    indexer, _, vector_store = make_indexer(tmp_path, items, {"1": "contenido"})

    indexer.start()
    wait_until_idle(indexer)
    indexer.start()
    wait_until_idle(indexer)

    assert len(vector_store.added) == 1


def test_stop_halts_processing_before_all_items_finish(tmp_path):
    items = [_item(str(i)) for i in range(20)]
    texts = {str(i): "contenido" for i in range(20)}
    indexer, _, _ = make_indexer(tmp_path, items, texts, delay=0.05)

    indexer.start()
    time.sleep(0.06)
    indexer.stop()
    wait_until_idle(indexer)

    assert indexer.status()["processed"] < 20


def test_starting_while_already_running_reports_already_running(tmp_path):
    items = [_item(str(i)) for i in range(5)]
    texts = {str(i): "contenido" for i in range(5)}
    indexer, _, _ = make_indexer(tmp_path, items, texts, delay=0.05)

    indexer.start()
    result = indexer.start()
    indexer.stop()
    wait_until_idle(indexer)

    assert result["status"] == "already_running"


def test_search_embeds_the_query_and_delegates_to_the_vector_store(tmp_path):
    indexer, embeddings, _ = make_indexer(tmp_path, [], {})

    results = indexer.search("una pregunta sobre el código", top_k=3)

    assert embeddings.calls == [(["una pregunta sobre el código"], "query")]
    assert results[0]["top_k"] == 3


def test_search_without_where_passes_none_through(tmp_path):
    # Pedido explícito (conversations_search sin project_id busca sobre todo
    # el historial, no solo un proyecto) — sin where, nunca se filtra.
    indexer, _, vector_store = make_indexer(tmp_path, [], {})
    indexer.search("una pregunta")
    assert vector_store.search_calls[0]["where"] is None


def test_search_with_where_filters_the_vector_store_query(tmp_path):
    # conversations_search(project_id=...) — el filtro real llega hasta
    # chromadb sin que KnowledgeIndexer conozca conversations en particular
    # (genérico, mismo motor que 'code').
    indexer, _, vector_store = make_indexer(tmp_path, [], {})
    indexer.search("una pregunta", where={"project_id": "proj-1"})
    assert vector_store.search_calls[0]["where"] == {"project_id": "proj-1"}


def test_manifest_summary_counts_items_by_status_without_scanning(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest = IndexManifest(manifest_path)
    data = {}
    manifest.mark(data, "1", "t1", STATUS_INDEXED, chunk_count=3)
    manifest.mark(data, "2", "t1", STATUS_ERROR, reason="boom")
    manifest.mark(data, "3", "t1", STATUS_SKIPPED_UNSUPPORTED)
    manifest.save(data)
    indexer, _, _ = make_indexer(tmp_path, [], {})

    summary = indexer.manifest_summary()

    assert summary == {"indexed": 1, "error": 1, "skipped_unsupported": 1, "total": 3}


def test_extra_metadata_from_the_item_is_merged_into_every_chunk(tmp_path):
    items = [_item("1", extra={"path": "snarf/core/orchestrator.py"})]
    indexer, _, vector_store = make_indexer(tmp_path, items, {"1": "contenido real"})

    indexer.start()
    wait_until_idle(indexer)

    _ids, _embeds, _docs, metadatas = vector_store.added[0]
    assert metadatas[0]["path"] == "snarf/core/orchestrator.py"
