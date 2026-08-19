import pytest
from types import SimpleNamespace

from snarf.capabilities.notion import Notion, format_properties_text


def make_notion(api_key="fake-token"):
    notion = Notion.__new__(Notion)
    notion._api_key = api_key
    return notion


def fake_response(json_data):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: json_data)


def test_available_is_false_without_api_key():
    assert make_notion(api_key=None).available is False


def test_available_is_true_with_api_key():
    assert make_notion().available is True


def test_search_raises_when_not_configured():
    with pytest.raises(RuntimeError):
        make_notion(api_key=None).search("algo")


def test_search_extracts_title_and_url_from_results(monkeypatch):
    from snarf.capabilities import notion as module

    payload = {
        "results": [
            {
                "id": "page-1",
                "object": "page",
                "url": "https://notion.so/page-1",
                "properties": {"title": {"type": "title", "title": [{"plain_text": "Mi página"}]}},
            }
        ]
    }
    monkeypatch.setattr(module.requests, "post", lambda *a, **k: fake_response(payload))
    results = make_notion().search("Mi página")
    assert results == [{"id": "page-1", "object": "page", "title": "Mi página", "url": "https://notion.so/page-1"}]


def test_create_page_sends_title_and_paragraph_blocks(monkeypatch):
    from snarf.capabilities import notion as module

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return fake_response({"id": "new-page", "url": "https://notion.so/new-page"})

    monkeypatch.setattr(module.requests, "post", fake_post)
    result = make_notion().create_page("parent-1", "Título nuevo", "primer párrafo\n\nsegundo párrafo")

    assert result == {"id": "new-page", "url": "https://notion.so/new-page"}
    sent = calls[0]["json"]
    assert sent["parent"] == {"page_id": "parent-1"}
    assert sent["properties"]["title"]["title"][0]["text"]["content"] == "Título nuevo"
    assert len(sent["children"]) == 2
    assert sent["children"][0]["paragraph"]["rich_text"][0]["text"]["content"] == "primer párrafo"


def test_read_page_text_joins_paragraph_blocks(monkeypatch):
    from snarf.capabilities import notion as module

    payload = {
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "primer párrafo"}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "segundo párrafo"}]}},
        ]
    }
    monkeypatch.setattr(module.requests, "get", lambda *a, **k: fake_response(payload))
    assert make_notion().read_page_text("page-1") == "primer párrafo\n\nsegundo párrafo"


def test_append_to_page_returns_status(monkeypatch):
    from snarf.capabilities import notion as module

    monkeypatch.setattr(module.requests, "patch", lambda *a, **k: fake_response({}))
    result = make_notion().append_to_page("page-1", "contenido nuevo")
    assert result == {"status": "appended", "page_id": "page-1"}


def test_get_database_raises_when_not_configured():
    with pytest.raises(RuntimeError):
        make_notion(api_key=None).get_database("db-1")


def test_get_database_returns_title_and_typed_property_schema(monkeypatch):
    from snarf.capabilities import notion as module

    payload = {
        "id": "db-1",
        "url": "https://notion.so/db-1",
        "title": [{"plain_text": "Mi Database"}],
        "properties": {
            "Name": {"type": "title"},
            "Status": {"type": "select"},
            "Due": {"type": "date"},
        },
    }
    monkeypatch.setattr(module.requests, "get", lambda *a, **k: fake_response(payload))
    result = make_notion().get_database("db-1")
    assert result == {
        "id": "db-1",
        "title": "Mi Database",
        "url": "https://notion.so/db-1",
        "properties": {"Name": "title", "Status": "select", "Due": "date"},
    }


def test_query_database_raises_when_not_configured():
    with pytest.raises(RuntimeError):
        make_notion(api_key=None).query_database("db-1")


def test_query_database_sends_filter_and_sorts_and_returns_typed_properties(monkeypatch):
    from snarf.capabilities import notion as module

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return fake_response(
            {
                "results": [
                    {
                        "id": "row-1",
                        "url": "https://notion.so/row-1",
                        "properties": {"Status": {"type": "select", "select": {"name": "Hecho"}}},
                    }
                ]
            }
        )

    monkeypatch.setattr(module.requests, "post", fake_post)
    filter_ = {"property": "Status", "select": {"equals": "Hecho"}}
    sorts = [{"property": "Due", "direction": "ascending"}]
    result = make_notion().query_database("db-1", filter=filter_, sorts=sorts)

    assert calls[0]["url"] == "https://api.notion.com/v1/databases/db-1/query"
    assert calls[0]["json"]["filter"] == filter_
    assert calls[0]["json"]["sorts"] == sorts
    assert result == [
        {
            "id": "row-1",
            "url": "https://notion.so/row-1",
            "properties": {"Status": {"type": "select", "select": {"name": "Hecho"}}},
        }
    ]


def test_create_database_item_sends_properties_untouched(monkeypatch):
    from snarf.capabilities import notion as module

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return fake_response({"id": "new-row", "url": "https://notion.so/new-row"})

    monkeypatch.setattr(module.requests, "post", fake_post)
    properties = {"Name": {"title": [{"text": {"content": "Nueva tarea"}}]}, "Status": {"select": {"name": "Por hacer"}}}
    result = make_notion().create_database_item("db-1", properties)

    assert result == {"id": "new-row", "url": "https://notion.so/new-row"}
    assert calls[0]["url"] == "https://api.notion.com/v1/pages"
    assert calls[0]["json"]["parent"] == {"database_id": "db-1"}
    assert calls[0]["json"]["properties"] == properties


def test_update_page_properties_sends_a_patch_with_the_properties(monkeypatch):
    from snarf.capabilities import notion as module

    calls = []

    def fake_patch(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return fake_response({})

    monkeypatch.setattr(module.requests, "patch", fake_patch)
    properties = {"Status": {"select": {"name": "Hecho"}}}
    result = make_notion().update_page_properties("page-1", properties)

    assert result == {"id": "page-1", "status": "updated"}
    assert calls[0]["url"] == "https://api.notion.com/v1/pages/page-1"
    assert calls[0]["json"] == {"properties": properties}


def test_iter_all_pages_paginates_until_has_more_is_false(monkeypatch):
    from snarf.capabilities import notion as module

    pages = [
        fake_response(
            {
                "results": [
                    {
                        "id": "page-1",
                        "url": "https://notion.so/page-1",
                        "last_edited_time": "2026-08-01T00:00:00.000Z",
                        "properties": {"title": {"type": "title", "title": [{"plain_text": "Uno"}]}},
                    }
                ],
                "has_more": True,
                "next_cursor": "cursor-1",
            }
        ),
        fake_response(
            {
                "results": [
                    {
                        "id": "page-2",
                        "url": "https://notion.so/page-2",
                        "last_edited_time": "2026-08-02T00:00:00.000Z",
                        "properties": {"title": {"type": "title", "title": [{"plain_text": "Dos"}]}},
                    }
                ],
                "has_more": False,
                "next_cursor": None,
            }
        ),
    ]
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return pages.pop(0)

    monkeypatch.setattr(module.requests, "post", fake_post)
    results = list(make_notion().iter_all_pages())

    assert [r["id"] for r in results] == ["page-1", "page-2"]
    assert results[0]["title"] == "Uno"
    assert calls[0]["filter"] == {"property": "object", "value": "page"}
    assert "start_cursor" not in calls[0]
    assert calls[1]["start_cursor"] == "cursor-1"


def test_iter_all_databases_filters_by_database_object(monkeypatch):
    from snarf.capabilities import notion as module

    payload = fake_response(
        {
            "results": [
                {
                    "id": "db-1",
                    "url": "https://notion.so/db-1",
                    "last_edited_time": "2026-08-01T00:00:00.000Z",
                    "title": [{"plain_text": "Mi Database"}],
                }
            ],
            "has_more": False,
            "next_cursor": None,
        }
    )
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return payload

    monkeypatch.setattr(module.requests, "post", fake_post)
    results = list(make_notion().iter_all_databases())

    assert results == [
        {"id": "db-1", "title": "Mi Database", "url": "https://notion.so/db-1", "last_edited_time": "2026-08-01T00:00:00.000Z"}
    ]
    assert calls[0]["filter"] == {"property": "object", "value": "database"}


def test_iter_database_rows_paginates_with_start_cursor(monkeypatch):
    from snarf.capabilities import notion as module

    pages = [
        fake_response(
            {
                "results": [{"id": "row-1", "url": "u1", "last_edited_time": "t1", "properties": {}}],
                "has_more": True,
                "next_cursor": "cursor-a",
            }
        ),
        fake_response(
            {
                "results": [{"id": "row-2", "url": "u2", "last_edited_time": "t2", "properties": {}}],
                "has_more": False,
                "next_cursor": None,
            }
        ),
    ]
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "json": json})
        return pages.pop(0)

    monkeypatch.setattr(module.requests, "post", fake_post)
    results = list(make_notion().iter_database_rows("db-1"))

    assert [r["id"] for r in results] == ["row-1", "row-2"]
    assert calls[0]["url"] == "https://api.notion.com/v1/databases/db-1/query"
    assert "start_cursor" not in calls[0]["json"]
    assert calls[1]["json"]["start_cursor"] == "cursor-a"


def test_format_properties_text_handles_common_property_types():
    properties = {
        "Título": {"type": "title", "title": [{"plain_text": "Mi nota"}]},
        "Estado": {"type": "select", "select": {"name": "Hecho"}},
        "Etiquetas": {"type": "multi_select", "multi_select": [{"name": "urgente"}, {"name": "casa"}]},
        "Vencimiento": {"type": "date", "date": {"start": "2026-08-20", "end": None}},
        "Prioridad": {"type": "number", "number": 3},
        "Archivado": {"type": "checkbox", "checkbox": True},
        "Vacío": {"type": "rich_text", "rich_text": []},
    }
    text = format_properties_text(properties)
    assert "Título: Mi nota" in text
    assert "Estado: Hecho" in text
    assert "Etiquetas: urgente, casa" in text
    assert "Vencimiento: 2026-08-20" in text
    assert "Prioridad: 3" in text
    assert "Archivado: sí" in text
    assert "Vacío" not in text
