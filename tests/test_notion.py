import pytest
from types import SimpleNamespace

from snarf.capabilities.notion import Notion


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
