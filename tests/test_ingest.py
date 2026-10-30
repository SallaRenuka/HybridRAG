from app.ingest import chunk_text, clean_text


def test_clean_text_removes_extra_whitespace():
    assert clean_text(" hello   world \n\n\n test ") == "hello world \n\n test"


def test_chunk_text_returns_chunks_with_overlap():
    text = "Sentence one. " * 250
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_invalid_chunk_settings_raise():
    import pytest
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=100, overlap=100)
