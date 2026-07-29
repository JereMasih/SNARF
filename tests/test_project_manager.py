from snarf.specialists.project_manager import ProjectManager


class FakeDrive:
    def __init__(self):
        self.folder_calls = []  # list of (name, parent_id)
        self._next_id = 0

    def get_or_create_folder(self, name, parent_id=None):
        self.folder_calls.append((name, parent_id))
        self._next_id += 1
        return f"folder-{self._next_id}"


class FakeLLM:
    def __init__(self, available=True, response="Investigación, Borradores", raise_error=False):
        self.available = available
        self._response = response
        self._raise_error = raise_error
        self.calls = []

    def generate(self, system, messages):
        self.calls.append((system, messages))
        if self._raise_error:
            raise RuntimeError("fallo simulado")
        return self._response


class FakeIndexer:
    def __init__(self):
        self.search_calls = []

    def search(self, query, top_k=5, where=None):
        self.search_calls.append({"query": query, "top_k": top_k, "where": where})
        return [{"id": "chunk-1", "text": "resultado"}]


def make_manager(tmp_path, monkeypatch, drive=None, llm=None, indexer=None):
    from snarf.specialists import project_manager as module

    monkeypatch.setattr(module, "PROJECTS_DIR", tmp_path / "projects")
    return ProjectManager(drive or FakeDrive(), indexer or FakeIndexer(), llm or FakeLLM(), "fundador")


def test_create_resolves_root_folder_once_across_multiple_creations(tmp_path, monkeypatch):
    drive = FakeDrive()
    manager = make_manager(tmp_path, monkeypatch, drive=drive)
    manager.create("Proyecto A")
    manager.create("Proyecto B")
    root_calls = [c for c in drive.folder_calls if c[0] in ("Snarf", "Proyectos")]
    assert root_calls == [("Snarf", None), ("Proyectos", "folder-1")]


def test_create_persists_a_well_shaped_record(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    record = manager.create("Newsletter de Trading")
    assert record["name"] == "Newsletter de Trading"
    assert record["prompt"] == ""
    assert record["drive_folder_id"]
    assert record["subfolders"] == {"Investigación": "folder-4", "Borradores": "folder-5"}
    assert record["tasks"] == []
    assert record["notes"] == []
    assert record["id"].startswith("newsletter-de-trading-")


def test_two_projects_with_the_same_display_name_get_different_drive_folders(tmp_path, monkeypatch):
    drive = FakeDrive()
    manager = make_manager(tmp_path, monkeypatch, drive=drive)
    manager.create("Finanzas")
    manager.create("Finanzas")
    project_folder_calls = [c for c in drive.folder_calls if c[0].startswith("Finanzas")]
    names = [c[0] for c in project_folder_calls]
    assert names[0] != names[1]  # nombres de carpeta distintos, nunca colisionan


def test_create_falls_back_to_a_default_subfolder_when_llm_is_unavailable(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch, llm=FakeLLM(available=False))
    record = manager.create("Proyecto X")
    assert record["subfolders"] == {"Archivos": "folder-4"}


def test_create_falls_back_to_a_default_subfolder_when_llm_raises(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch, llm=FakeLLM(raise_error=True))
    record = manager.create("Proyecto X")
    assert record["subfolders"] == {"Archivos": "folder-4"}


def test_list_projects_is_empty_before_any_creation(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    assert manager.list_projects() == []


def test_list_projects_reflects_task_and_note_counts(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    record = manager.create("Proyecto")
    manager.add_task(record["id"], "hacer algo")
    manager.add_note(record["id"], "una nota")
    summaries = manager.list_projects()
    assert summaries[0]["task_count"] == 1
    assert summaries[0]["note_count"] == 1


def test_get_returns_none_for_a_missing_project(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    assert manager.get("no-existe") is None


def test_get_normalizes_a_corrupted_partial_record(tmp_path, monkeypatch):
    from snarf.specialists import project_manager as module

    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(module, "PROJECTS_DIR", projects_dir)
    projects_dir.mkdir(parents=True)
    (projects_dir / "broken-1.json").write_text(
        '{"name": "Roto", "tasks": [{"id": "t1"}, "no-es-un-dict"], "subfolders": {"X": 5}}',
        encoding="utf-8",
    )
    manager = ProjectManager(FakeDrive(), FakeIndexer(), FakeLLM(), "fundador")
    record = manager.get("broken-1")
    assert record["name"] == "Roto"
    assert record["tasks"] == [{"id": "t1", "text": "", "done": False}]
    assert record["subfolders"] == {}
    assert record["notes"] == []
    assert isinstance(record["created_at"], float)


def test_set_prompt_persists_and_returns_none_for_missing_project(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    record = manager.create("Proyecto")
    updated = manager.set_prompt(record["id"], "sos el asistente de este proyecto")
    assert updated["prompt"] == "sos el asistente de este proyecto"
    assert manager.set_prompt("no-existe", "x") is None


def test_add_complete_and_delete_task_roundtrip(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    record = manager.create("Proyecto")
    project_id = record["id"]
    updated = manager.add_task(project_id, "primera tarea")
    task_id = updated["tasks"][0]["id"]
    assert updated["tasks"][0]["done"] is False

    toggled = manager.complete_task(project_id, task_id)
    assert toggled["tasks"][0]["done"] is True
    toggled_again = manager.complete_task(project_id, task_id)
    assert toggled_again["tasks"][0]["done"] is False

    deleted = manager.delete_task(project_id, task_id)
    assert deleted["tasks"] == []


def test_add_and_delete_note_roundtrip(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    record = manager.create("Proyecto")
    project_id = record["id"]
    updated = manager.add_note(project_id, "una nota")
    note_id = updated["notes"][0]["id"]
    deleted = manager.delete_note(project_id, note_id)
    assert deleted["notes"] == []


def test_delete_removes_the_local_record_and_never_touches_drive(tmp_path, monkeypatch):
    drive = FakeDrive()
    manager = make_manager(tmp_path, monkeypatch, drive=drive)
    record = manager.create("Proyecto")
    calls_before_delete = list(drive.folder_calls)
    result = manager.delete(record["id"])
    assert result == {"status": "deleted", "project_id": record["id"]}
    assert manager.get(record["id"]) is None
    assert drive.folder_calls == calls_before_delete  # ninguna llamada nueva a Drive


def test_search_within_delegates_to_the_indexer_scoped_by_project_id(tmp_path, monkeypatch):
    indexer = FakeIndexer()
    manager = make_manager(tmp_path, monkeypatch, indexer=indexer)
    results = manager.search_within("proj-1", "impuestos", top_k=3)
    assert results == [{"id": "chunk-1", "text": "resultado"}]
    assert indexer.search_calls == [{"query": "impuestos", "top_k": 3, "where": {"project_id": "proj-1"}}]
