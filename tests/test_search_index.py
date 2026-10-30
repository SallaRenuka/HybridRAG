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
