import pytest
from unittest.mock import patch
from app.ingest import Chunk
from app.search_index import HybridIndex
from app.retriever import Retriever
from app.main import (
    INSUFFICIENT_INFO_MESSAGE,
    format_context_and_citation_map,
    process_answer_and_citations,
)
from app.evaluation import (
    EvalSample,
    evaluate_retrieval,
    compute_citation_metrics,
    compute_answer_faithfulness,
)


@pytest.fixture(scope="module")
def populated_index():
    """Populate a reproducible multi-document, multi-page test index."""
    chunks = [
        # Document 1: FastAPI framework (2 pages)
        Chunk(
            chunk_id="doc1_fastapi::p1::c0",
            text="FastAPI is an asynchronous web framework for Python that utilizes Starlette for high performance routing.",
            source="doc1_fastapi.txt",
            page=1,
        ),
        Chunk(
            chunk_id="doc1_fastapi::p2::c0",
            text="FastAPI includes a built-in dependency injection system that simplifies authentication and database session management.",
            source="doc1_fastapi.txt",
            page=2,
        ),
        # Document 2: Information Retrieval & Search (3 pages)
        Chunk(
            chunk_id="doc2_search::p1::c0",
            text="Vector embeddings map text into dense numerical spaces where inner products approximate conceptual semantic similarity.",
            source="doc2_search.pdf",
            page=1,
        ),
        Chunk(
            chunk_id="doc2_search::p2::c0",
            text="BM25Okapi is a probabilistic ranking algorithm that calculates term frequency and inverse document frequency with length normalization.",
            source="doc2_search.pdf",
            page=2,
        ),
        Chunk(
            chunk_id="doc2_search::p3::c0",
            text="Reciprocal Rank Fusion combines ranked lists from multiple search algorithms using the formula score = sum(1 / (60 + rank)).",
            source="doc2_search.pdf",
            page=3,
        ),
        # Document 3: Persistent Database
        Chunk(
            chunk_id="doc3_database::p0::c0",
            text="PostgreSQL is an enterprise ACID relational database that supports pgvector for persistent vector similarity queries.",
            source="doc3_database.txt",
            page=None,
        ),
    ]

    index = HybridIndex()
    index.build(chunks, batch_size=6)
    return index


# -------------------------------------------------------------------------
# Scenario 1: Questions with answers explicitly present in documents
# -------------------------------------------------------------------------
def test_scenario_1_explicit_fact_present(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False)
    results = retriever.retrieve("What formula does Reciprocal Rank Fusion use to combine rankings?", top_k=1)
    
    assert len(results) > 0
    top_chunk = results[0]["chunk"]
    assert top_chunk.chunk_id == "doc2_search::p3::c0"
    assert "score = sum(1 / (60 + rank))" in top_chunk.text
    assert top_chunk.page == 3


# -------------------------------------------------------------------------
# Scenario 2: Questions requiring information from multiple pages
# -------------------------------------------------------------------------
def test_scenario_2_multipage_synthesis(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False, max_chunks_per_source_page=1)
    results = retriever.retrieve("Explain FastAPI routing performance and its dependency injection system", top_k=3)
    
    retrieved_chunk_ids = {r["chunk"].chunk_id for r in results}
    # Both Page 1 and Page 2 of doc1_fastapi must be retrieved
    assert "doc1_fastapi::p1::c0" in retrieved_chunk_ids
    assert "doc1_fastapi::p2::c0" in retrieved_chunk_ids

    # Format context and simulate synthesis response using assigned citation IDs
    _, cit_map = format_context_and_citation_map(results)
    id_p1 = next(cid for cid, c in cit_map.items() if c.chunk_id == "doc1_fastapi::p1::c0")
    id_p2 = next(cid for cid, c in cit_map.items() if c.chunk_id == "doc1_fastapi::p2::c0")
    simulated_answer = (
        f"FastAPI achieves high performance routing via Starlette [{id_p1}]. "
        f"It manages authentication and sessions through its dependency injection system [{id_p2}]."
    )
    ans, citations = process_answer_and_citations(simulated_answer, cit_map)
    assert ans == simulated_answer
    assert len(citations) == 2
    cited_ids = {c.id for c in citations}
    assert cited_ids == {id_p1, id_p2}


# -------------------------------------------------------------------------
# Scenario 3: Questions requiring multiple documents
# -------------------------------------------------------------------------
def test_scenario_3_multidoc_synthesis(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False)
    results = retriever.retrieve("How does FastAPI connect with PostgreSQL database and pgvector?", top_k=3)
    
    sources = {r["chunk"].source for r in results}
    assert "doc1_fastapi.txt" in sources
    assert "doc3_database.txt" in sources


# -------------------------------------------------------------------------
# Scenario 4: Questions with no answer in the documents
# -------------------------------------------------------------------------
def test_scenario_4_unanswerable_out_of_domain(populated_index):
    # With a calibrated relevance score cutoff, completely irrelevant questions return no chunks
    retriever = Retriever(index=populated_index, use_reranker=False)
    
    # Simulate LLM answering an unanswerable question
    results = retriever.retrieve("What is the boiling point of liquid nitrogen?", top_k=3)
    _, cit_map = format_context_and_citation_map(results)

    # When the model outputs the required fallback
    raw_answer = INSUFFICIENT_INFO_MESSAGE
    ans, citations = process_answer_and_citations(raw_answer, cit_map)
    
    assert ans == INSUFFICIENT_INFO_MESSAGE
    assert citations == []  # Citations MUST be cleared on fallback!


# -------------------------------------------------------------------------
# Scenario 5: Questions containing exact keywords
# -------------------------------------------------------------------------
def test_scenario_5_exact_keyword_query(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False)
    # Exact keyword 'BM25Okapi'
    results = retriever.retrieve("BM25Okapi probabilistic ranking length normalization", top_k=1)
    assert len(results) > 0
    assert results[0]["chunk"].chunk_id == "doc2_search::p2::c0"


# -------------------------------------------------------------------------
# Scenario 6: Questions using different wording from the source (semantic paraphrase)
# -------------------------------------------------------------------------
def test_scenario_6_paraphrased_semantic_query(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False)
    # Paraphrased semantic query for dense vectors:
    results = retriever.retrieve("How can machines represent sentences using numerical coordinates for meaning?", top_k=1)
    assert len(results) > 0
    assert results[0]["chunk"].chunk_id == "doc2_search::p1::c0"


# -------------------------------------------------------------------------
# Scenario 7: Incorrect or unsupported citation detection
# -------------------------------------------------------------------------
def test_scenario_7_unsupported_citation_detection(populated_index):
    c1 = Chunk(chunk_id="c1", text="PostgreSQL supports ACID transactions.", source="db.txt", page=1)
    _, cit_map = format_context_and_citation_map([{"chunk": c1}])

    # Case A: Answer references non-existent citation ID [42]
    ans_a, cits_a = process_answer_and_citations("PostgreSQL is good [42].", cit_map)
    assert ans_a == INSUFFICIENT_INFO_MESSAGE
    assert cits_a == []

    # Case B: Answer cites [1] but claims completely unsupported hallucinated facts
    ans_b, cits_b = process_answer_and_citations("PostgreSQL was designed by NASA to fly Apollo 11 [1].", cit_map)
    assert ans_b == INSUFFICIENT_INFO_MESSAGE
    assert cits_b == []


# -------------------------------------------------------------------------
# Comprehensive Evaluation Benchmark Execution
# -------------------------------------------------------------------------
def test_comprehensive_evaluation_benchmark(populated_index):
    retriever = Retriever(index=populated_index, use_reranker=False)

    benchmark_samples = [
        EvalSample(
            query="What formula does Reciprocal Rank Fusion use?",
            expected_chunk_ids=["doc2_search::p3::c0"],
            expected_sources=["doc2_search.pdf"],
        ),
        EvalSample(
            query="How does BM25Okapi calculate ranking scores?",
            expected_chunk_ids=["doc2_search::p2::c0"],
            expected_sources=["doc2_search.pdf"],
        ),
        EvalSample(
            query="Explain dense numerical vector embeddings for meaning",
            expected_chunk_ids=["doc2_search::p1::c0"],
            expected_sources=["doc2_search.pdf"],
        ),
        EvalSample(
            query="What is FastAPI's routing based on?",
            expected_chunk_ids=["doc1_fastapi::p1::c0"],
            expected_sources=["doc1_fastapi.txt"],
        ),
        EvalSample(
            query="Does PostgreSQL support pgvector and ACID transactions?",
            expected_chunk_ids=["doc3_database::p0::c0"],
            expected_sources=["doc3_database.txt"],
        ),
    ]

    metrics = evaluate_retrieval(benchmark_samples, retriever, top_k=3)
    
    # Assert measurable retrieval performance
    assert metrics["mean_recall_at_1"] >= 0.80, f"Expected Recall@1 >= 0.80, got {metrics['mean_recall_at_1']}"
    assert metrics["mean_recall_at_3"] == 1.0, f"Expected Recall@3 == 1.0, got {metrics['mean_recall_at_3']}"
    assert metrics["mean_mrr"] >= 0.85, f"Expected MRR >= 0.85, got {metrics['mean_mrr']}"

    print("\n================ EVALUATION BENCHMARK RESULTS ================")
    print(f"Evaluated Queries:    {metrics['evaluated_queries']}")
    print(f"Mean Recall@1:        {metrics['mean_recall_at_1'] * 100:.1f}%")
    print(f"Mean Recall@3:        {metrics['mean_recall_at_3'] * 100:.1f}%")
    print(f"Mean MRR:             {metrics['mean_mrr']:.4f}")
    print("==============================================================")
