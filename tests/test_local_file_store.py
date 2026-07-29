from snarf.capabilities.local_file_store import LocalFileStore


def test_save_writes_real_bytes_to_disk(tmp_path):
    store = LocalFileStore(tmp_path / "archivos")
    path = store.save("nota.md", b"contenido real")
    assert path.read_bytes() == b"contenido real"


def test_save_creates_the_base_directory_if_missing(tmp_path):
    base_dir = tmp_path / "no-existe-todavia"
    store = LocalFileStore(base_dir)
    store.save("a.txt", b"x")
    assert base_dir.exists()


def test_is_always_available():
    assert LocalFileStore(None).available is True
