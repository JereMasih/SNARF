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


def test_append_derives_a_real_slug_from_the_title(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Un Título con Ñ y Acentós!", "c", "r", source_ref="x", path=path)
    assert entry["slug"] == "un-titulo-con-n-y-acentos"


def test_append_deduplicates_colliding_slugs(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    first = blog.append("Mismo título", "c", "r", source_ref="x", path=path)
    second = blog.append("Mismo título", "c", "r", source_ref="x", path=path)
    assert first["slug"] == "mismo-titulo"
    assert second["slug"] == "mismo-titulo-2"


def test_list_all_includes_drafts_and_published(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    blog.append("Borrador", "c", "r", source_ref="x", public=False, path=path)
    blog.append("Publicado", "c", "r", source_ref="x", public=True, path=path)
    titles = {a["title"] for a in blog.list_all(path=path)}
    assert titles == {"Borrador", "Publicado"}


def test_get_finds_an_article_by_id_or_by_slug(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Encontrame", "c", "r", source_ref="x", path=path)
    assert blog.get(entry["id"], path=path)["title"] == "Encontrame"
    assert blog.get(entry["slug"], path=path)["title"] == "Encontrame"
    assert blog.get("no-existe", path=path) is None


def test_update_edits_fields_without_changing_the_slug(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Original", "cuerpo viejo", "resumen viejo", source_ref="x", path=path)
    updated = blog.update(entry["id"], path=path, title="Editado", body="cuerpo nuevo", public=True)
    assert updated["title"] == "Editado"
    assert updated["body"] == "cuerpo nuevo"
    assert updated["public"] is True
    assert updated["slug"] == entry["slug"]
    assert blog.get(entry["id"], path=path)["title"] == "Editado"


def test_update_returns_none_for_a_missing_article(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    assert blog.update("no-existe", path=path, title="x") is None


def test_delete_removes_a_real_article(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Para borrar", "c", "r", source_ref="x", path=path)
    assert blog.delete(entry["id"], path=path) is True
    assert blog.get(entry["id"], path=path) is None


def test_delete_returns_false_for_a_missing_article(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    assert blog.delete("no-existe", path=path) is False


def test_append_without_cover_image_defaults_to_none(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Sin portada", "c", "r", source_ref="x", path=path)
    assert entry["cover_image"] is None


def test_append_and_update_cover_image(tmp_path):
    path = tmp_path / "blog_posts.jsonl"
    entry = blog.append("Con portada", "c", "r", source_ref="x", cover_image="/blog/assets/a.png", path=path)
    assert entry["cover_image"] == "/blog/assets/a.png"
    updated = blog.update(entry["id"], path=path, cover_image="/blog/assets/b.png")
    assert updated["cover_image"] == "/blog/assets/b.png"
    assert blog.get(entry["id"], path=path)["cover_image"] == "/blog/assets/b.png"
