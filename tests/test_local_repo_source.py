from snarf.knowledge.local_repo_source import LocalRepoKnowledgeSource


def _write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_iter_items_finds_python_files_under_snarf_and_tests(tmp_path):
    _write(tmp_path / "snarf" / "core" / "orchestrator.py", "print('real')")
    _write(tmp_path / "tests" / "test_x.py", "def test_x(): pass")
    source = LocalRepoKnowledgeSource(root=tmp_path)

    ids = {item.id for item in source.iter_items()}

    assert "snarf/core/orchestrator.py" in ids
    assert "tests/test_x.py" in ids


def test_iter_items_finds_adr_files(tmp_path):
    _write(tmp_path / "adr" / "0001-algo.md", "# ADR 0001")
    source = LocalRepoKnowledgeSource(root=tmp_path)

    ids = {item.id for item in source.iter_items()}

    assert "adr/0001-algo.md" in ids


def test_iter_items_finds_only_the_named_root_docs(tmp_path):
    _write(tmp_path / "FOUNDATION.md", "# FOUNDATION")
    _write(tmp_path / "README_UNRELATED.md", "no debería contarse")
    source = LocalRepoKnowledgeSource(root=tmp_path)

    ids = {item.id for item in source.iter_items()}

    assert "FOUNDATION.md" in ids
    assert "README_UNRELATED.md" not in ids


def test_iter_items_never_yields_a_duplicate_id(tmp_path):
    _write(tmp_path / "CLAUDE.md", "# CLAUDE")
    source = LocalRepoKnowledgeSource(root=tmp_path)

    ids = [item.id for item in source.iter_items()]

    assert len(ids) == len(set(ids))


def test_read_item_returns_the_real_file_content(tmp_path):
    _write(tmp_path / "adr" / "0001-algo.md", "contenido real del ADR")
    source = LocalRepoKnowledgeSource(root=tmp_path)
    item = next(iter(source.iter_items()))

    assert source.read_item(item) == "contenido real del ADR"


def test_mime_type_is_python_for_py_files_and_markdown_otherwise(tmp_path):
    _write(tmp_path / "snarf" / "core" / "orchestrator.py", "x = 1")
    _write(tmp_path / "adr" / "0001-algo.md", "# ADR")
    source = LocalRepoKnowledgeSource(root=tmp_path)

    by_id = {item.id: item for item in source.iter_items()}

    assert by_id["snarf/core/orchestrator.py"].mime_type == "text/x-python"
    assert by_id["adr/0001-algo.md"].mime_type == "text/markdown"


def test_modified_marker_changes_when_the_file_is_rewritten(tmp_path):
    import os

    path = tmp_path / "adr" / "0001-algo.md"
    _write(path, "v1")
    source = LocalRepoKnowledgeSource(root=tmp_path)
    marker_1 = next(iter(source.iter_items())).modified_marker

    path.write_text("v2 con más contenido", encoding="utf-8")
    # Filesystems locales (HFS+/APFS) pueden tener resolución de mtime de 1s
    # — forzar el nuevo mtime en vez de confiar en el reloj real evita un
    # test intermitente (flaky) por escribir dos veces dentro del mismo tick.
    new_mtime = path.stat().st_mtime + 5
    os.utime(path, (new_mtime, new_mtime))
    marker_2 = next(iter(source.iter_items())).modified_marker

    assert marker_1 != marker_2


def test_domain_is_code():
    assert LocalRepoKnowledgeSource.domain == "code"
