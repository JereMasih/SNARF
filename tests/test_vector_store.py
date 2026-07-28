from snarf.knowledge.vector_store import VectorStore


def make_store(tmp_path):
    return VectorStore(persist_directory=str(tmp_path / "chroma"))


def test_add_and_search_returns_the_closest_match(tmp_path):
    store = make_store(tmp_path)
    store.add(
        ids=["a:0", "b:0"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        documents=["contenido A", "contenido B"],
        metadatas=[{"file_id": "a"}, {"file_id": "b"}],
    )
    results = store.search([1.0, 0.0], top_k=1)
    assert results[0]["text"] == "contenido A"
    assert results[0]["metadata"]["file_id"] == "a"


def test_delete_by_file_id_removes_only_that_files_chunks(tmp_path):
    store = make_store(tmp_path)
    store.add(
        ids=["a:0", "b:0"],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        documents=["contenido A", "contenido B"],
        metadatas=[{"file_id": "a"}, {"file_id": "b"}],
    )
    store.delete_by_file_id("a")
    assert store.count() == 1


def test_add_with_no_ids_is_a_safe_no_op(tmp_path):
    store = make_store(tmp_path)
    store.add(ids=[], embeddings=[], documents=[], metadatas=[])
    assert store.count() == 0


def test_constructing_a_store_does_not_touch_disk(tmp_path):
    # Construir VectorStore no debe crear el directorio de persistencia hasta
    # el primer uso real (mismo criterio que GoogleDrive._client()).
    persist_dir = tmp_path / "nunca-usado"
    VectorStore(persist_directory=str(persist_dir))
    assert not persist_dir.exists()
