import pytest
from app.ingest import Chunk
from app.main import (
    Citation,
    INSUFFICIENT_INFO_MESSAGE,
    extract_claim_tokens,
    verify_claim_support,
    format_context_and_citation_map,
    process_answer_and_citations,
)


def test_extract_claim_tokens_removes_brackets_and_stopwords():
    tokens = extract_claim_tokens("FastAPI is a Python framework for high performance APIs [1][2].")
    assert "fastapi" in tokens
    assert "framework" in tokens
    assert "apis" in tokens
    assert "is" not in tokens
    assert "a" not in tokens
    assert "for" not in tokens
    assert "[1]" not in tokens


def test_verify_claim_support_valid():
    chunk_text = "FastAPI is a modern web framework for building APIs with Python and Pydantic validation."
    claim = "FastAPI uses Pydantic for API data validation [1]."
    assert verify_claim_support(claim, chunk_text) is True


def test_verify_claim_support_unsupported():
    chunk_text = "FastAPI is a modern web framework for building APIs with Python."
    # Fabricated claim about Albert Einstein and Quantum mechanics
    hallucinated_claim = "FastAPI was developed by Albert Einstein for Quantum Physics [1]."
    assert verify_claim_support(hallucinated_claim, chunk_text) is False


def test_format_context_and_citation_map():
    c1 = Chunk(chunk_id="c1", text="Chunk one text.", source="guide.pdf", page=3)
    c2 = Chunk(chunk_id="c2", text="Chunk two text.", source="readme.txt", page=None)
    results = [{"chunk": c1}, {"chunk": c2}]

    context_str, cit_map = format_context_and_citation_map(results)
    assert "[1] Source: guide.pdf | Page 3" in context_str
    assert "[2] Source: readme.txt | Page N/A" in context_str
    assert len(cit_map) == 2
    assert cit_map[1].id == 1
    assert cit_map[1].source == "guide.pdf"
    assert cit_map[1].page == 3
    assert cit_map[2].id == 2
    assert cit_map[2].source == "readme.txt"
    assert cit_map[2].page is None


def test_process_answer_and_citations_success():
    c1 = Chunk(chunk_id="c1", text="HybridRAG uses BM25 and FAISS for search.", source="doc.pdf", page=1)
    c2 = Chunk(chunk_id="c2", text="PostgreSQL stores metadata.", source="db.txt", page=None)
    results = [{"chunk": c1}, {"chunk": c2}]
    _, cit_map = format_context_and_citation_map(results)

    raw_answer = "HybridRAG combines BM25 and FAISS for search [1]."
    ans, citations = process_answer_and_citations(raw_answer, cit_map)

    assert ans == raw_answer
    # Only chunk 1 was cited and verified; chunk 2 must not be present
    assert len(citations) == 1
    assert citations[0].id == 1
    assert citations[0].chunk_id == "c1"


def test_process_answer_and_citations_insufficient_fallback():
    cit_map = {1: Citation(id=1, source="doc.pdf", chunk_id="c1", page=1, text="Text.")}
    ans, citations = process_answer_and_citations(
        "I could not find sufficient information in the uploaded documents.",
        cit_map,
    )
    assert ans == INSUFFICIENT_INFO_MESSAGE
    assert citations == []


def test_process_answer_and_citations_rejects_invalid_citation_ids():
    c1 = Chunk(chunk_id="c1", text="Information about search.", source="doc.pdf", page=1)
    _, cit_map = format_context_and_citation_map([{"chunk": c1}])

    # Cites invalid [99] which does not exist in context
    raw_answer = "Some factual claim about quantum physics [99]."
    ans, citations = process_answer_and_citations(raw_answer, cit_map)

    # Invalid citation rejected; no verified evidence -> fallback triggered!
    assert ans == INSUFFICIENT_INFO_MESSAGE
    assert citations == []


def test_process_answer_and_citations_rejects_hallucinated_claim():
    c1 = Chunk(chunk_id="c1", text="Python is a dynamic programming language.", source="doc.pdf", page=1)
    _, cit_map = format_context_and_citation_map([{"chunk": c1}])

    # Cites [1], but claim is completely unsupported by chunk 1
    raw_answer = "Python was created by Galileo Galilei to study Jupiter's moons [1]."
    ans, citations = process_answer_and_citations(raw_answer, cit_map)

    # Verification fails on claim evidence -> fallback triggered!
    assert ans == INSUFFICIENT_INFO_MESSAGE
    assert citations == []
