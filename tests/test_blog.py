from snarf.telemetry import blog


def test_append_and_list_public_roundtrip(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append(
        "Título real", "cuerpo real", "resumen real", source_ref="research:trend_scan:abc123",
        public=True, tags=["ia"], path=path,
    )
    articles = blog.list_public(path=path)
    assert len(articles) == 1
    assert articles[0]["id"] == entry["id"]
    assert articles[0]["title"] == "Título real"
    assert articles[0]["tags"] == ["ia"]


def test_unpublished_articles_are_never_listed(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    blog.append("Borrador", "cuerpo", "resumen", source_ref="research:abc", public=False, path=path)
    assert blog.list_public(path=path) == []


def test_list_public_sorts_newest_first(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    blog.append("Primero", "c", "r", source_ref="research:1", public=True, path=path)
    blog.append("Segundo", "c", "r", source_ref="research:2", public=True, path=path)
    titles = [a["title"] for a in blog.list_public(path=path)]
    assert titles == ["Segundo", "Primero"]


def test_list_public_with_no_file_is_empty(tmp_path):
    assert blog.list_public(path=tmp_path / "no_existe.jsonl") == []
