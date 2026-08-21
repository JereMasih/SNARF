import json

import pytest

from snarf.specialists.second_brain import SecondBrainManager


class FakeNotion:
    def __init__(self):
        self.query_database_calls = []
        self.databases = {}  # database_id -> list of rows
        self.pages = {}  # page_id -> page dict
        self.database_schemas = {}  # database_id -> {"properties": {name: type}}
        self.create_database_item_calls = []
        self.create_database_item_result = {"id": "new-row", "url": "https://notion.so/new-row"}
        self.create_page_calls = []
        self.create_database_calls = []
        self._next_database_id = 0
        self.all_databases = []  # para iter_all_databases (onboarding, ADR 0190)

    def query_database(self, database_id, filter=None, sorts=None, page_size=100):
        self.query_database_calls.append({"database_id": database_id, "filter": filter})
        return self.databases.get(database_id, [])

    def get_page(self, page_id):
        if page_id not in self.pages:
            raise RuntimeError("not found")
        return self.pages[page_id]

    def get_database(self, database_id):
        return self.database_schemas[database_id]

    def create_database_item(self, database_id, properties):
        self.create_database_item_calls.append({"database_id": database_id, "properties": properties})
        return self.create_database_item_result

    def create_page(self, parent_page_id, title, content=""):
        self.create_page_calls.append({"parent_page_id": parent_page_id, "title": title, "content": content})
        return {"id": "root-page-1", "url": "https://notion.so/root-page-1"}

    def create_database(self, parent_page_id, title, properties):
        self._next_database_id += 1
        database_id = f"db-{self._next_database_id}"
        self.create_database_calls.append({"parent_page_id": parent_page_id, "title": title, "properties": properties})
        return {"id": database_id, "url": f"https://notion.so/{database_id}"}

    def iter_all_databases(self):
        yield from self.all_databases


class FakeLLM:
    def __init__(self, available=True, response="Análisis real del Área.", raise_error=False):
        self.available = available
        self._response = response
        self._raise_error = raise_error
        self.calls = []

    def generate(self, system, messages):
        self.calls.append({"system": system, "messages": messages})
        if self._raise_error:
            raise RuntimeError("fallo simulado")
        from snarf.capabilities.anthropic_llm import LLMResponse

        return LLMResponse(text=self._response, speech=self._response)


def make_row(row_id, name, extra_properties=None):
    properties = {"Nombre": {"type": "title", "title": [{"plain_text": name}]}}
    properties.update(extra_properties or {})
    return {"id": row_id, "url": f"https://notion.so/{row_id}", "properties": properties}


def test_database_map_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.get_database_map() == {
        "areas": None,
        "proyectos": None,
        "recursos": None,
        "archivo": None,
        "property_map": {},
    }


def test_save_and_get_database_map_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )
    result = manager.get_database_map()
    assert result["areas"] == "db-areas"
    assert result["proyectos"] == "db-proyectos"
    assert result["recursos"] is None
    assert result["property_map"] == {"proyecto_area_relation": "Área"}


def test_save_database_map_ignores_unknown_keys_and_bad_property_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    saved = manager.save_database_map({"areas": "db-1", "garbage": "x", "property_map": "not-a-dict"})
    assert "garbage" not in saved
    assert saved["property_map"] == {}


def test_database_map_is_namespaced_per_user(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    SecondBrainManager(FakeNotion(), "fundador").save_database_map({"areas": "db-fundador"})
    SecondBrainManager(FakeNotion(), "otro-usuario").save_database_map({"areas": "db-otro"})

    assert SecondBrainManager(FakeNotion(), "fundador").get_database_map()["areas"] == "db-fundador"
    assert SecondBrainManager(FakeNotion(), "otro-usuario").get_database_map()["areas"] == "db-otro"
    assert (tmp_path / "data" / "second_brain" / "fundador" / "database_map.json").exists()
    assert (tmp_path / "data" / "second_brain" / "otro-usuario" / "database_map.json").exists()


def test_is_connected_requires_areas_and_proyectos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.is_connected() is False

    manager.save_database_map({"areas": "db-areas"})
    assert manager.is_connected() is False

    manager.save_database_map({"areas": "db-areas", "proyectos": "db-proyectos"})
    assert manager.is_connected() is True


def test_list_areas_returns_empty_when_not_mapped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.list_areas() == []


def test_list_areas_returns_row_summaries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.databases["db-areas"] = [make_row("area-1", "Salud"), make_row("area-2", "SNARF")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"areas": "db-areas"})

    result = manager.list_areas()
    assert [r["name"] for r in result] == ["Salud", "SNARF"]
    assert result[0]["id"] == "area-1"
    assert result[0]["url"] == "https://notion.so/area-1"


def test_get_area_returns_none_when_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.get_area("nope") is None


def test_get_area_returns_none_when_archived(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.pages["area-1"] = {"id": "area-1", "url": "u", "archived": True, "properties": {}}
    manager = SecondBrainManager(notion, "fundador")
    assert manager.get_area("area-1") is None


def test_get_area_returns_summary_when_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.pages["area-1"] = {
        "id": "area-1",
        "url": "https://notion.so/area-1",
        "archived": False,
        "properties": {"Nombre": {"type": "title", "title": [{"plain_text": "Salud"}]}},
    }
    manager = SecondBrainManager(notion, "fundador")
    result = manager.get_area("area-1")
    assert result["name"] == "Salud"
    assert result["id"] == "area-1"


def test_list_projects_without_area_id_queries_without_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.databases["db-proyectos"] = [make_row("proj-1", "Campaña Q3")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"proyectos": "db-proyectos"})

    result = manager.list_projects()
    assert [r["name"] for r in result] == ["Campaña Q3"]
    assert notion.query_database_calls[0]["filter"] is None


def test_list_projects_with_area_id_raises_without_relation_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"proyectos": "db-proyectos"})

    with pytest.raises(ValueError):
        manager.list_projects(area_id="area-1")


def test_list_projects_with_area_id_filters_by_mapped_relation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.databases["db-proyectos"] = [make_row("proj-1", "Campaña Q3")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {"proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    result = manager.list_projects(area_id="area-1")
    assert [r["name"] for r in result] == ["Campaña Q3"]
    assert notion.query_database_calls[0]["filter"] == {
        "property": "Área",
        "relation": {"contains": "area-1"},
    }


def test_list_resources_returns_empty_when_not_mapped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.list_resources("proj-1") == []


def test_list_resources_raises_without_relation_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"recursos": "db-recursos"})

    with pytest.raises(ValueError):
        manager.list_resources("proj-1")


def test_list_resources_filters_by_mapped_relation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.databases["db-recursos"] = [make_row("res-1", "Imagen de referencia")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {"recursos": "db-recursos", "property_map": {"recurso_proyecto_relation": "Proyecto"}}
    )

    result = manager.list_resources("proj-1")
    assert [r["name"] for r in result] == ["Imagen de referencia"]
    assert notion.query_database_calls[0]["filter"] == {
        "property": "Proyecto",
        "relation": {"contains": "proj-1"},
    }


def test_list_archive_filters_by_mapped_relation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.databases["db-archivo"] = [make_row("arch-1", "Nota vieja")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {"archivo": "db-archivo", "property_map": {"archivo_proyecto_relation": "Proyecto"}}
    )

    result = manager.list_archive("proj-1")
    assert [r["name"] for r in result] == ["Nota vieja"]


def test_create_project_row_returns_none_when_not_connected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.create_project_row("Proyecto") is None


def test_create_project_row_returns_none_without_proyectos_mapped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    manager.save_database_map({"areas": "db-areas"})
    assert manager.create_project_row("Proyecto") is None


def test_create_project_row_creates_item_using_the_real_title_property(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.database_schemas["db-proyectos"] = {"properties": {"Nombre": "title", "Estado": "select"}}
    notion.create_database_item_result = {"id": "notion-page-1", "url": "https://notion.so/notion-page-1"}
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"areas": "db-areas", "proyectos": "db-proyectos"})

    result = manager.create_project_row("Campaña Q3")

    assert result == "notion-page-1"
    assert notion.create_database_item_calls == [
        {
            "database_id": "db-proyectos",
            "properties": {"Nombre": {"title": [{"text": {"content": "Campaña Q3"}}]}},
        }
    ]


def test_create_project_row_returns_none_when_no_title_property(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.database_schemas["db-proyectos"] = {"properties": {"Estado": "select"}}
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map({"areas": "db-areas", "proyectos": "db-proyectos"})
    assert manager.create_project_row("Campaña Q3") is None


def test_get_project_mirrors_get_area_behavior(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.pages["proj-1"] = {
        "id": "proj-1",
        "url": "https://notion.so/proj-1",
        "archived": False,
        "properties": {"Nombre": {"type": "title", "title": [{"plain_text": "Campaña Q3"}]}},
    }
    manager = SecondBrainManager(notion, "fundador")
    assert manager.get_project("proj-1")["name"] == "Campaña Q3"
    assert manager.get_project("no-existe") is None


def _setup_area_with_projects(notion):
    notion.pages["area-1"] = {
        "id": "area-1",
        "url": "https://notion.so/area-1",
        "archived": False,
        "properties": {"Nombre": {"type": "title", "title": [{"plain_text": "Salud"}]}},
    }
    notion.databases["db-proyectos"] = [make_row("proj-1", "Rutina"), make_row("proj-2", "Nutrición")]


def test_get_area_home_returns_none_for_missing_area(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.get_area_home("no-existe") is None


def test_get_area_home_marks_resources_and_archive_unmapped_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    home = manager.get_area_home("area-1")
    assert home["area"]["name"] == "Salud"
    assert [p["name"] for p in home["projects"]] == ["Rutina", "Nutrición"]
    assert home["resources_mapped"] is False
    assert home["resources"] == []
    assert home["archive_mapped"] is False
    assert home["archive"] == []


def test_get_area_home_aggregates_resources_and_archive_across_projects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    notion.databases["db-recursos"] = [make_row("res-1", "Plan de rutina")]
    notion.databases["db-archivo"] = [make_row("arch-1", "Rutina vieja")]
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {
            "areas": "db-areas",
            "proyectos": "db-proyectos",
            "recursos": "db-recursos",
            "archivo": "db-archivo",
            "property_map": {
                "proyecto_area_relation": "Área",
                "recurso_proyecto_relation": "Proyecto",
                "archivo_proyecto_relation": "Proyecto",
            },
        }
    )

    home = manager.get_area_home("area-1")
    assert home["resources_mapped"] is True
    # Un ítem de recursos por cada uno de los 2 proyectos (mismo mock de query_database para ambos)
    assert len(home["resources"]) == 2
    assert home["archive_mapped"] is True
    assert len(home["archive"]) == 2


def test_generate_area_report_without_llm_factory_says_so_explicitly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    manager = SecondBrainManager(notion, "fundador")
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    report = manager.generate_area_report("area-1")
    assert "falta configurar el modelo de lenguaje" in report["report"]
    assert isinstance(report["report_generated_at"], float)


def test_generate_area_report_uses_llm_with_real_data_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    llm = FakeLLM(response="Salud tiene 2 proyectos activos.")
    manager = SecondBrainManager(notion, "fundador", llm_factory=lambda: llm)
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    report = manager.generate_area_report("area-1")
    assert report["report"] == "Salud tiene 2 proyectos activos."
    sent_content = llm.calls[0]["messages"][0]["content"]
    assert "Rutina" in sent_content
    assert "Nutrición" in sent_content
    assert "sin mapear todavía" in sent_content  # recursos/archivo no mapeados


def test_generate_area_report_degrades_gracefully_on_llm_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    llm = FakeLLM(raise_error=True)
    manager = SecondBrainManager(notion, "fundador", llm_factory=lambda: llm)
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    report = manager.generate_area_report("area-1")
    assert "No se pudo generar el reporte" in report["report"]


def test_cached_area_report_generates_once_then_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    _setup_area_with_projects(notion)
    llm = FakeLLM(response="Reporte real.")
    manager = SecondBrainManager(notion, "fundador", llm_factory=lambda: llm)
    manager.save_database_map(
        {"areas": "db-areas", "proyectos": "db-proyectos", "property_map": {"proyecto_area_relation": "Área"}}
    )

    first = manager.cached_area_report("area-1")
    second = manager.cached_area_report("area-1")

    assert first["report"] == "Reporte real."
    assert second["report"] == "Reporte real."
    assert len(llm.calls) == 1  # segunda llamada usó el cache, no volvió a generar


def test_cached_area_report_returns_none_for_missing_area(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = SecondBrainManager(FakeNotion(), "fundador")
    assert manager.cached_area_report("no-existe") is None


def test_auto_build_workspace_creates_root_page_and_four_databases(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    manager = SecondBrainManager(notion, "fundador")

    result = manager.auto_build_workspace("parent-page-real")

    assert result["root_page_id"] == "root-page-1"
    assert notion.create_page_calls[0]["parent_page_id"] == "parent-page-real"
    assert notion.create_page_calls[0]["title"] == "Snarf Second Brain"

    titles = [c["title"] for c in notion.create_database_calls]
    assert titles == ["Áreas", "Proyectos", "Recursos", "Archivo"]
    assert all(c["parent_page_id"] == "root-page-1" for c in notion.create_database_calls)

    # Proyectos se relaciona con Áreas, Recursos/Archivo con Proyectos —
    # cada relación apunta al id REAL devuelto por la database anterior, no
    # a un id inventado.
    proyectos_call = notion.create_database_calls[1]
    assert proyectos_call["properties"]["Área"]["relation"]["database_id"] == "db-1"
    recursos_call = notion.create_database_calls[2]
    assert recursos_call["properties"]["Proyecto"]["relation"]["database_id"] == "db-2"
    archivo_call = notion.create_database_calls[3]
    assert archivo_call["properties"]["Proyecto"]["relation"]["database_id"] == "db-2"


def test_auto_build_workspace_saves_a_complete_database_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    manager = SecondBrainManager(notion, "fundador")

    result = manager.auto_build_workspace("parent-page-real")

    saved = manager.get_database_map()
    assert saved == result["database_map"]
    assert saved["areas"] == "db-1"
    assert saved["proyectos"] == "db-2"
    assert saved["recursos"] == "db-3"
    assert saved["archivo"] == "db-4"
    assert saved["property_map"] == {
        "proyecto_area_relation": "Área",
        "recurso_proyecto_relation": "Proyecto",
        "archivo_proyecto_relation": "Proyecto",
    }
    assert manager.is_connected() is True


def test_suggest_mapping_returns_empty_suggestions_without_matching_databases(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.all_databases = [{"id": "db-x", "title": "Otra cosa", "url": "u", "last_edited_time": "t"}]
    manager = SecondBrainManager(notion, "fundador")

    result = manager.suggest_mapping()
    assert result["suggestions"] == {}
    assert result["all_databases"] == notion.all_databases


def test_suggest_mapping_matches_databases_by_keyword_and_never_saves_on_its_own(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    notion = FakeNotion()
    notion.all_databases = [
        {"id": "db-areas", "title": "Mis Áreas de vida", "url": "u1", "last_edited_time": "t"},
        {"id": "db-proyectos", "title": "Projects 2026", "url": "u2", "last_edited_time": "t"},
        {"id": "db-recursos", "title": "Recursos varios", "url": "u3", "last_edited_time": "t"},
    ]
    manager = SecondBrainManager(notion, "fundador")

    result = manager.suggest_mapping()
    assert result["suggestions"]["areas"]["id"] == "db-areas"
    assert result["suggestions"]["proyectos"]["id"] == "db-proyectos"
    assert result["suggestions"]["recursos"]["id"] == "db-recursos"
    assert "archivo" not in result["suggestions"]
    # Nunca guarda nada por su cuenta — quien llama debe confirmar con
    # save_database_map() antes de que tenga efecto real.
    assert manager.is_connected() is False
