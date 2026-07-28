from snarf.knowledge.chunking import chunk_text


def test_empty_text_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_text_shorter_than_chunk_size_is_a_single_chunk():
    assert chunk_text("hola mundo", chunk_size=100) == ["hola mundo"]


def test_long_text_is_split_with_overlap_between_consecutive_chunks():
    text = "a" * 250
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) == 3
    assert chunks[0] == "a" * 100


def test_chunks_reassemble_into_the_full_original_text():
    text = "0123456789" * 10  # 100 caracteres
    overlap = 5
    chunks = chunk_text(text, chunk_size=30, overlap=overlap)
    rebuilt = chunks[0]
    for chunk in chunks[1:]:
        rebuilt += chunk[overlap:]
    assert rebuilt == text
