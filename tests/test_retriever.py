import pytest
from unittest.mock import MagicMock
from app.ingest import Chunk
from app.search_index import HybridIndex
from app.retriever import Retriever, compute_jaccard_similarity


def test_compute_jaccard_similarity():
    s1 = {"fastapi", "python", "backend"}
    s2 = {"fastapi", "python", "database"}
    # intersection: 2 ('fastapi', 'python'), union: 4 ('fastapi', 'python', 'backend', 'database') -> 0.5
    assert compute_jaccard_similarity(s1, s2) == 0.5
    assert compute_jaccard_similarity(set(), s2) == 0.0
    assert compute_jaccard_similarity(s1, s1) == 1.0


def test_deduplicate_drops_same_page_redundant_chunks():
    c1 = Chunk(chunk_id="doc1::p1::c0", text="FastAPI is a modern web framework for Python APIs.", source="doc1.pdf", page=1)
    # c2 is 90% overlapping sliding window chunk on page 1
    c2 = Chunk(chunk_id="doc1::p1::c1", text="FastAPI is a modern web framework for Python APIs and services.", source="doc1.pdf", page=1)
    # c3 is on page 2 (different evidence)
    c3 = Chunk(chunk_id="doc1::p2::c0", text="Authentication in FastAPI is configured with OAuth2 and JWT tokens.", source="doc1.pdf", page=2)

    candidates = [
        {"chunk": c1, "rerank_score": 5.0},
        {"chunk": c2, "rerank_score": 4.8},
        {"chunk": c3, "rerank_score": 4.5},
    ]

    retriever = Retriever(index=MagicMock(), use_reranker=False, similarity_threshold=0.75)
    selected = retriever.deduplicate_and_diversify(candidates, top_k=3)

    # c2 should be dropped due to similarity with c1 on page 1; c3 on page 2 must be preserved!
    assert len(selected) == 2
    assert selected[0]["chunk"].chunk_id == "doc1::p1::c0"
    assert selected[1]["chunk"].chunk_id == "doc1::p2::c0"


def test_deduplicate_preserves_multidoc_and_multipage():
    # Chunks from two different documents and different pages
    c_doc1_p1 = Chunk(chunk_id="doc1::p1::c0", text="Deep learning utilizes neural networks for representation learning.", source="doc1.pdf", page=1)
    c_doc1_p2 = Chunk(chunk_id="doc1::p2::c0", text="Convolutional neural networks excel at spatial image recognition.", source="doc1.pdf", page=2)
    c_doc2_p1 = Chunk(chunk_id="doc2::p1::c0", text="Recurrent neural networks process sequential temporal data.", source="doc2.pdf", page=1)

    candidates = [
        {"chunk": c_doc1_p1, "rerank_score": 6.0},
        {"chunk": c_doc1_p2, "rerank_score": 5.5},
        {"chunk": c_doc2_p1, "rerank_score": 5.0},
    ]

    retriever = Retriever(index=MagicMock(), use_reranker=False)
    selected = retriever.deduplicate_and_diversify(candidates, top_k=3)

    assert len(selected) == 3
    sources = {item["chunk"].source for item in selected}
    pages = {item["chunk"].page for item in selected}
    assert sources == {"doc1.pdf", "doc2.pdf"}
    assert pages == {1, 2}


def test_score_threshold_filters_irrelevant_chunks():
    c1 = Chunk(chunk_id="c1", text="Relevant machine learning text.", source="a.txt", page=1)
    c2 = Chunk(chunk_id="c2", text="Completely irrelevant cooking recipe.", source="b.txt", page=1)

    candidates = [
        {"chunk": c1, "rerank_score": 2.5},
        {"chunk": c2, "rerank_score": -6.0},
    ]

    retriever = Retriever(index=MagicMock(), use_reranker=False)
    # Threshold at -2.0 should drop c2
    selected = retriever.deduplicate_and_diversify(candidates, top_k=3, score_threshold=-2.0)
    assert len(selected) == 1
    assert selected[0]["chunk"].chunk_id == "c1"

    # If threshold is strict (e.g. 5.0), all are dropped
    assert retriever.deduplicate_and_diversify(candidates, top_k=3, score_threshold=5.0) == []


def test_retrieve_empty_query():
    retriever = Retriever(index=MagicMock(), use_reranker=False)
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_retrieve_with_mocked_reranker():
    mock_index = MagicMock()
    c1 = Chunk(chunk_id="c1", text="Python programming guide.", source="a.txt", page=1)
    c2 = Chunk(chunk_id="c2", text="Java programming language.", source="b.txt", page=1)
    mock_index.hybrid_search.return_value = [
        {"chunk": c1, "rrf_score": 0.03},
        {"chunk": c2, "rrf_score": 0.02},
    ]

    retriever = Retriever(index=mock_index, use_reranker=True)
    mock_model = MagicMock()
    # Score Java higher than Python for a Java query
    mock_model.predict.return_value = [1.2, 7.8]
    retriever._reranker = mock_model

    results = retriever.retrieve("Java syntax", top_k=2)
    assert len(results) == 2
    # Reranker reordered: c2 (Java) is now rank 1!
    assert results[0]["chunk"].chunk_id == "c2"
    assert results[0]["rerank_score"] == 7.8
    assert results[1]["chunk"].chunk_id == "c1"
    assert results[1]["rerank_score"] == 1.2


def test_reranker_failure_fallback_to_rrf():
    mock_index = MagicMock()
    c1 = Chunk(chunk_id="c1", text="Top RRF ranked chunk.", source="a.txt", page=1)
    c2 = Chunk(chunk_id="c2", text="Second RRF ranked chunk.", source="b.txt", page=1)
    mock_index.hybrid_search.return_value = [
        {"chunk": c1, "rrf_score": 0.035},
        {"chunk": c2, "rrf_score": 0.015},
    ]

    retriever = Retriever(index=mock_index, use_reranker=True)
    mock_model = MagicMock()
    # Simulate runtime exception in CrossEncoder (e.g. CUDA OOM or device failure)
    mock_model.predict.side_effect = RuntimeError("Simulated device failure in CrossEncoder")
    retriever._reranker = mock_model

    # Must NOT crash! Must gracefully fall back to RRF rankings
    results = retriever.retrieve("Any question", top_k=2)
    assert len(results) == 2
    assert results[0]["chunk"].chunk_id == "c1"
    assert results[0]["rrf_score"] == 0.035
    assert results[1]["chunk"].chunk_id == "c2"
    assert results[1]["rrf_score"] == 0.015
