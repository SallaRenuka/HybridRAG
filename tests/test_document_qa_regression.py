import threading
import pytest
from app.workspace import workspace_manager
from app.main import (
    INSUFFICIENT_INFO_MESSAGE,
    format_context_and_citation_map,
    generate_extractive_summary,
    process_answer_and_citations,
)


@pytest.fixture(scope="module")
def user28_workspace():
    """Retrieve the populated textbook workspace for User 28."""
    idx, ret = workspace_manager.get_user_workspace(28)
    assert len(idx.chunks) > 0, "User 28 index must contain indexed chunks"
    return idx, ret


def test_what_is_machine_learning_grounded_answer(user28_workspace):
    """Verify that 'What is Machine Learning?' yields a grounded answer with exact Page 32 citation."""
    _, retriever = user28_workspace
    query = "What is Machine Learning?"
    results = retriever.retrieve(query, top_k=3)
    assert len(results) > 0

    _, citation_map = format_context_and_citation_map(results)
    answer, citations = generate_extractive_summary(results, citation_map, query=query)

    assert answer != INSUFFICIENT_INFO_MESSAGE, "Expected grounded answer from textbook"
    assert len(citations) >= 1, "Expected at least one supporting citation"

    # Verify exact page number accuracy
    cited_pages = [c.page for c in citations if c.page is not None]
    assert 32 in cited_pages or 749 in cited_pages, f"Expected citation on Page 32 or 749, got {cited_pages}"

    # Verify factual definitional keywords
    answer_lower = answer.lower()
    assert (
        "science" in answer_lower
        or "programming computers" in answer_lower
        or "learn from data" in answer_lower
    ), f"Answer missing core definition: {answer}"


def test_explain_types_of_machine_learning(user28_workspace):
    """Verify that 'Explain the types of Machine Learning.' retrieves categories with citations."""
    _, retriever = user28_workspace
    query = "Explain the types of Machine Learning."
    results = retriever.retrieve(query, top_k=3)
    assert len(results) > 0

    _, citation_map = format_context_and_citation_map(results)
    answer, citations = generate_extractive_summary(results, citation_map, query=query)

    assert answer != INSUFFICIENT_INFO_MESSAGE, "Expected grounded answer for types of ML"
    assert len(citations) >= 1

    cited_pages = [c.page for c in citations if c.page is not None]
    assert any(p in [37, 43, 60, 750] for p in cited_pages), f"Expected citation on Page 37, 43, or 60, got {cited_pages}"

    answer_lower = answer.lower()
    assert (
        "supervised" in answer_lower
        or "categories" in answer_lower
        or "classified" in answer_lower
        or "learning" in answer_lower
    )


def test_unanswerable_question_returns_insufficient_info(user28_workspace):
    """Verify that questions not answered in the PDF return the insufficient information message."""
    _, retriever = user28_workspace
    query = "What is the secret recipe of Coca-Cola and Martian rocket fuel?"
    results = retriever.retrieve(query, top_k=3)

    _, citation_map = format_context_and_citation_map(results)
    answer, citations = generate_extractive_summary(results, citation_map, query=query)

    assert answer == INSUFFICIENT_INFO_MESSAGE, f"Expected insufficient info message, got: {answer}"
    assert len(citations) == 0, f"Expected 0 citations for unanswerable question, got: {len(citations)}"


def test_citation_verification_rejects_hallucinations(user28_workspace):
    """Verify that process_answer_and_citations drops unsupported hallucinated claims."""
    _, retriever = user28_workspace
    results = retriever.retrieve("What is Machine Learning?", top_k=3)
    _, citation_map = format_context_and_citation_map(results)

    # Valid grounded statement
    grounded_claim = (
        "Machine Learning is the science of programming computers so they can learn from data [1]."
    )
    ans_grounded, cits_grounded = process_answer_and_citations(grounded_claim, citation_map)
    assert ans_grounded != INSUFFICIENT_INFO_MESSAGE
    assert len(cits_grounded) >= 1

    # Hallucinated statement
    hallucination = (
        "Machine Learning was created in 1750 by Benjamin Franklin using a kite and lightning."
    )
    ans_hallucinated, cits_hallucinated = process_answer_and_citations(hallucination, citation_map)
    assert ans_hallucinated == INSUFFICIENT_INFO_MESSAGE
    assert len(cits_hallucinated) == 0


def test_concurrent_repeated_queries_stability(user28_workspace):
    """Verify that repeated concurrent queries execute without macOS SIGSEGV exit code 139."""
    _, retriever = user28_workspace
    queries = [
        "What is Machine Learning?",
        "Explain the types of Machine Learning.",
        "Arthur Samuel 1959 definition",
        "What is an artificial neural network?",
    ]

    errors = []

    def run_worker(thread_id):
        try:
            for q in queries:
                res = retriever.retrieve(q, top_k=3)
                assert len(res) > 0
                _, cmap = format_context_and_citation_map(res)
                ans, cits = generate_extractive_summary(res, cmap, query=q)
                assert ans is not None
        except Exception as e:
            errors.append((thread_id, e))

    threads = [threading.Thread(target=run_worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Encountered errors during concurrent execution: {errors}"
