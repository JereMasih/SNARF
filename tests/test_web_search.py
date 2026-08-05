import pytest
import requests

from snarf.capabilities.web_search import TavilySearch


def test_unavailable_without_a_real_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert TavilySearch().available is False


def test_available_with_a_real_api_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-real")
    assert TavilySearch().available is True


def test_search_raises_without_a_real_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        TavilySearch().search("algo")


def test_search_parses_a_real_shaped_response(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-real")

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "answer": "respuesta sintetizada",
                "results": [
                    {"title": "Título 1", "url": "https://x.com/1", "content": "contenido 1", "score": 0.9},
                    {"title": "Título 2", "url": "https://x.com/2", "content": "contenido 2", "score": 0.8},
                ],
            }

    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = TavilySearch().search("noticias reales", max_results=3)

    assert result["answer"] == "respuesta sintetizada"
    assert len(result["results"]) == 2
    assert result["results"][0] == {"title": "Título 1", "url": "https://x.com/1", "content": "contenido 1"}
    assert captured["json"]["query"] == "noticias reales"
    assert captured["json"]["max_results"] == 3
    assert captured["json"]["api_key"] == "tvly-real"


def test_search_propagates_a_real_http_error(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-real")

    class _FailingResponse:
        def raise_for_status(self):
            raise requests.HTTPError("401 real de Tavily")

    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FailingResponse())

    with pytest.raises(requests.HTTPError):
        TavilySearch().search("algo")
