import pytest
from app.ingest import Chunk
from app.search_index import HybridIndex, tokenize


def test_tokenize_preserves_identifiers():
    tokens = tokenize("HybridRAG error_code_404 in app/main.py:42")
    assert "hybridrag" in tokens
    assert "error_code_404" in tokens
    assert "app/main.py:42" in tokens


def test_build_empty_chunks():
    index = HybridIndex()
    count = index.build([])
    assert count == 0
    assert index.faiss_index is None
    assert index.bm25 is None
    assert index.vector_search("test") == []
    assert index.keyword_search("test") == []
    assert index.hybrid_search("test") == []


def test_build_and_search_with_chunks():
    chunks = [
        Chunk(
            chunk_id="doc1::p1::c0",
            text="FastAPI is a modern web framework for building APIs with Python.",
            source="doc1.txt",
            page=1,
        ),
        Chunk(
            chunk_id="doc1::p1::c1",
            text="FAISS provides efficient similarity search and clustering of dense vectors.",
            source="doc1.txt",
            page=1,
        ),
        Chunk(
            chunk_id="doc1::p2::c0",
            text="BM25 is a ranking function used in information retrieval for keyword search.",
            source="doc1.txt",
            page=2,
        ),
    ]

    index = HybridIndex()
    count = index.build(chunks, batch_size=2)
    assert count == 3
    assert index.faiss_index is not None
    assert index.bm25 is not None
    assert index.faiss_index.ntotal == 3

    # Vector search test
    vector_results = index.vector_search("vector similarity clustering", limit=2)
    assert len(vector_results) > 0
    # Top vector result should be chunk 1 (FAISS)
    assert vector_results[0][0] == 1

    # Keyword search test
    keyword_results = index.keyword_search("FastAPI", limit=2)
    assert len(keyword_results) > 0
    # Top keyword result should be chunk 0 (FastAPI)
    assert keyword_results[0][0] == 0

    # Hybrid search test
    hybrid_results = index.hybrid_search("information retrieval BM25", limit_each=2)
    assert len(hybrid_results) > 0
    assert hybrid_results[0]["chunk"].chunk_id == "doc1::p2::c0"


def test_save_empty_index_returns_false(tmp_path):
    index = HybridIndex()
    assert index.save(tmp_path) is False
    assert not (tmp_path / "metadata.json").exists()
    assert not (tmp_path / "faiss.index").exists()


def test_save_and_load_round_trip(tmp_path):
    chunks = [
        Chunk(chunk_id="c1", text="Python asynchronous web servers with FastAPI.", source="a.txt", page=1),
        Chunk(chunk_id="c2", text="Information retrieval using BM25 and vector spaces.", source="b.txt", page=2),
    ]

    # Build and save
    original_index = HybridIndex()
    original_index.build(chunks)
    assert original_index.save(tmp_path) is True

    # Files must exist on disk
    assert (tmp_path / "metadata.json").exists()
    assert (tmp_path / "faiss.index").exists()

    # Load into a fresh index instance
    loaded_index = HybridIndex()
    assert loaded_index.load(tmp_path) is True
    assert len(loaded_index.chunks) == 2
    assert loaded_index.chunks[0].chunk_id == "c1"
    assert loaded_index.chunks[1].chunk_id == "c2"

    # Search consistency check
    orig_vec = original_index.vector_search("FastAPI Python", limit=2)
    loaded_vec = loaded_index.vector_search("FastAPI Python", limit=2)
    assert orig_vec == loaded_vec

    orig_kw = original_index.keyword_search("BM25 retrieval", limit=2)
    loaded_kw = loaded_index.keyword_search("BM25 retrieval", limit=2)
    assert orig_kw == loaded_kw


def test_load_nonexistent_or_empty_directory(tmp_path):
    index = HybridIndex()
    non_existent = tmp_path / "does_not_exist"
    assert index.load(non_existent) is False

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert index.load(empty_dir) is False


def test_load_incompatible_or_corrupt_metadata(tmp_path):
    import json
    chunks = [Chunk(chunk_id="c1", text="Test text passage.", source="a.txt", page=1)]
    idx = HybridIndex()
    idx.build(chunks)
    assert idx.save(tmp_path) is True

    meta_file = tmp_path / "metadata.json"

    # 1. Corrupt JSON syntax
    with open(meta_file, "w") as f:
        f.write("{invalid json content")
    fresh_idx = HybridIndex()
    assert fresh_idx.load(tmp_path) is False

    # 2. Incompatible schema version
    with open(meta_file, "w") as f:
        json.dump({"schema_version": 999, "embedding_model": idx.embedding_model_name, "chunk_count": 1, "chunks": []}, f)
    assert fresh_idx.load(tmp_path) is False

    # 3. Incompatible embedding model
    with open(meta_file, "w") as f:
        json.dump({"schema_version": 1, "embedding_model": "different/model", "chunk_count": 1, "chunks": []}, f)
    assert fresh_idx.load(tmp_path) is False
