from snarf.knowledge.notion_source import NotionSource


class FakeNotion:
    def __init__(self, pages=None, databases=None, rows_by_database=None, bodies=None):
        self._pages = pages or []
        self._databases = databases or []
        self._rows_by_database = rows_by_database or {}
        self._bodies = bodies or {}

    def iter_all_pages(self):
        yield from self._pages

    def iter_all_databases(self):
        yield from self._databases

    def iter_database_rows(self, database_id):
        yield from self._rows_by_database.get(database_id, [])

    def read_page_text(self, page_id):
        return self._bodies.get(page_id, "")


def test_domain_is_personal_same_as_drive():
    assert NotionSource(FakeNotion()).domain == "personal"


def test_iter_items_yields_a_knowledge_item_per_page():
    notion = FakeNotion(
        pages=[{"id": "page-1", "title": "Mi página", "url": "https://notion.so/page-1", "last_edited_time": "t1"}]
    )
    items = list(NotionSource(notion).iter_items())

    assert len(items) == 1
    item = items[0]
    assert item.id == "page-1"
    assert item.name == "Mi página"
    assert item.modified_marker == "t1"
    assert item.extra_metadata == {"location": "notion", "notion_url": "https://notion.so/page-1"}


def test_iter_items_yields_a_knowledge_item_per_database_row():
    notion = FakeNotion(
        databases=[{"id": "db-1", "title": "Tareas", "url": "https://notion.so/db-1", "last_edited_time": "t0"}],
        rows_by_database={
            "db-1": [
                {
                    "id": "row-1",
                    "url": "https://notion.so/row-1",
                    "last_edited_time": "t1",
                    "properties": {"Título": {"type": "title", "title": [{"plain_text": "Comprar café"}]}},
                }
            ]
        },
    )
    items = list(NotionSource(notion).iter_items())

    assert len(items) == 1
    item = items[0]
    assert item.id == "row-1"
    assert item.name == "Comprar café"
    assert item.extra_metadata == {
        "location": "notion",
        "notion_url": "https://notion.so/row-1",
        "notion_database_id": "db-1",
    }


def test_row_without_title_property_falls_back_to_id():
    notion = FakeNotion(
        databases=[{"id": "db-1", "title": "Tareas", "url": "u", "last_edited_time": "t0"}],
        rows_by_database={"db-1": [{"id": "row-1", "url": "u1", "last_edited_time": "t1", "properties": {}}]},
    )
    items = list(NotionSource(notion).iter_items())
    assert items[0].name == "row-1"


def test_read_item_for_a_plain_page_returns_only_the_body():
    notion = FakeNotion(
        pages=[{"id": "page-1", "title": "Mi página", "url": "u", "last_edited_time": "t1"}],
        bodies={"page-1": "cuerpo real de la página"},
    )
    source = NotionSource(notion)
    items = list(source.iter_items())
    assert source.read_item(items[0]) == "cuerpo real de la página"


def test_read_item_for_a_database_row_combines_properties_and_body():
    notion = FakeNotion(
        databases=[{"id": "db-1", "title": "Tareas", "url": "u", "last_edited_time": "t0"}],
        rows_by_database={
            "db-1": [
                {
                    "id": "row-1",
                    "url": "u1",
                    "last_edited_time": "t1",
                    "properties": {
                        "Título": {"type": "title", "title": [{"plain_text": "Comprar café"}]},
                        "Estado": {"type": "select", "select": {"name": "Pendiente"}},
                    },
                }
            ]
        },
        bodies={"row-1": "notas adicionales en el cuerpo"},
    )
    source = NotionSource(notion)
    items = list(source.iter_items())
    text = source.read_item(items[0])

    assert "Título: Comprar café" in text
    assert "Estado: Pendiente" in text
    assert "notas adicionales en el cuerpo" in text


def test_row_properties_cache_resets_on_each_new_iter_items_call():
    notion = FakeNotion(
        databases=[{"id": "db-1", "title": "Tareas", "url": "u", "last_edited_time": "t0"}],
        rows_by_database={
            "db-1": [{"id": "row-1", "url": "u1", "last_edited_time": "t1", "properties": {}}]
        },
    )
    source = NotionSource(notion)
    list(source.iter_items())
    # Una segunda corrida sin ese database ya no debería arrastrar el row
    # viejo en el cache interno de properties.
    notion._databases = []
    notion._rows_by_database = {}
    list(source.iter_items())

    assert source._row_properties == {}
