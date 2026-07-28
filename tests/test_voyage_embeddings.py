from types import SimpleNamespace

from snarf.capabilities.voyage_embeddings import VoyageEmbeddings


def make_embeddings(fake_client):
    emb = VoyageEmbeddings.__new__(VoyageEmbeddings)
    emb.model = "voyage-4-lite"
    emb._api_key = "fake"
    emb._client = fake_client
    return emb


def test_embed_returns_vectors_and_records_usage(monkeypatch):
    from snarf.capabilities import voyage_embeddings as module

    fake_result = SimpleNamespace(embeddings=[[0.1, 0.2], [0.3, 0.4]], total_tokens=42)
    fake_client = SimpleNamespace(embed=lambda texts, model, input_type: fake_result)
    recorded = []
    monkeypatch.setattr(module.usage_tracker, "record_voyage_call", lambda model, tokens, **k: recorded.append((model, tokens)))

    emb = make_embeddings(fake_client)
    vectors = emb.embed(["texto uno", "texto dos"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert recorded == [("voyage-4-lite", 42)]


def test_embed_without_api_key_raises_a_clear_error():
    emb = VoyageEmbeddings.__new__(VoyageEmbeddings)
    emb.model = "voyage-4-lite"
    emb._client = None
    try:
        emb.embed(["texto"])
        assert False, "debería haber lanzado RuntimeError"
    except RuntimeError as exc:
        assert "VOYAGE_API_KEY" in str(exc)


def test_available_reflects_whether_the_client_was_built():
    emb = VoyageEmbeddings.__new__(VoyageEmbeddings)
    emb._client = None
    assert emb.available is False
    emb._client = object()
    assert emb.available is True
