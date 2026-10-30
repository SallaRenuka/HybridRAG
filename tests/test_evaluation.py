import pytest
from unittest.mock import MagicMock
from app.ingest import Chunk
from app.main import Citation
from app.evaluation import (
    EvalSample,
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_citation_metrics,
    compute_answer_faithfulness,
    evaluate_retrieval,
)


def test_compute_recall_at_k():
    retrieved = ["c1", "c2", "c3"]
    expected = ["c2", "c4"]
    # At k=1: retrieved has ["c1"], expected has ["c2", "c4"] -> 0 / 2 = 0.0
    assert compute_recall_at_k(retrieved, expected, k=1) == 0.0
    # At k=2: retrieved has ["c1", "c2"], intersection is {"c2"} -> 1 / 2 = 0.5
    assert compute_recall_at_k(retrieved, expected, k=2) == 0.5
    # At k=3: retrieved has ["c1", "c2", "c3"], intersection is {"c2"} -> 1 / 2 = 0.5
    assert compute_recall_at_k(retrieved, expected, k=3) == 0.5


def test_compute_reciprocal_rank():
    # Target chunk is at rank 1 -> RR = 1.0
    assert compute_reciprocal_rank(["c1", "c2", "c3"], ["c1"]) == 1.0
    # Target chunk is at rank 2 -> RR = 0.5
    assert compute_reciprocal_rank(["c1", "c2", "c3"], ["c2"]) == 0.5
    # Target chunk is at rank 3 -> RR = 1/3
    assert pytest.approx(compute_reciprocal_rank(["c1", "c2", "c3"], ["c3"])) == 1.0 / 3.0
    # Target chunk not retrieved -> RR = 0.0
    assert compute_reciprocal_rank(["c1", "c2", "c3"], ["c99"]) == 0.0


def test_compute_citation_metrics():
    c1 = Citation(id=1, source="docA.pdf", chunk_id="c1", page=1, text="Text A.")
    c2 = Citation(id=2, source="docB.pdf", chunk_id="c2", page=2, text="Text B.")

    # Returned [docA, docB], expected [docA]
    # Precision: 1 hit / 2 returned = 0.5. Recall: 1 hit / 1 expected = 1.0.
    prec, rec = compute_citation_metrics([c1, c2], ["docA.pdf"])
    assert prec == 0.5
    assert rec == 1.0

    # Returned [docA], expected [docA, docC]
    # Precision: 1 / 1 = 1.0. Recall: 1 / 2 = 0.5.
    prec, rec = compute_citation_metrics([c1], ["docA.pdf", "docC.pdf"])
    assert prec == 1.0
    assert rec == 0.5


def test_compute_answer_faithfulness():
    c1 = Citation(id=1, source="a.txt", chunk_id="c1", page=1, text="FastAPI is an asynchronous web framework for Python.")
    
    # 100% faithful: claim is supported by c1
    ans_faithful = "FastAPI is an asynchronous Python web framework [1]."
    assert compute_answer_faithfulness(ans_faithful, [c1]) == 1.0

    # Unfaithful: claim cites c1 but fabricates alien tech
    ans_unfaithful = "FastAPI was discovered in 1840 on planet Mars by astronomers [1]."
    assert compute_answer_faithfulness(ans_unfaithful, [c1]) == 0.0


def test_evaluate_retrieval_runner():
    mock_retriever = MagicMock()
    mock_retriever.retrieve.side_effect = [
        [{"chunk": Chunk("c1", "text", "a.txt", 1)}, {"chunk": Chunk("c2", "text", "b.txt", 2)}],
        [{"chunk": Chunk("c3", "text", "c.txt", 1)}, {"chunk": Chunk("c1", "text", "a.txt", 1)}],
    ]

    samples = [
        EvalSample(query="Q1", expected_chunk_ids=["c1"], expected_sources=["a.txt"]),
        EvalSample(query="Q2", expected_chunk_ids=["c1"], expected_sources=["a.txt"]),
    ]

    results = evaluate_retrieval(samples, mock_retriever, top_k=2)
    assert results["evaluated_queries"] == 2
    # Q1: rank 1 (RR=1.0). Q2: rank 2 (RR=0.5) -> MRR = (1.0 + 0.5) / 2 = 0.75
    assert results["mean_mrr"] == 0.75
    # Q1 recall@1 = 1.0, Q2 recall@1 = 0.0 -> mean = 0.5
    assert results["mean_recall_at_1"] == 0.5
