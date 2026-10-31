from __future__ import annotations

import re
import pytest
from fastapi.testclient import TestClient

from app.main import app, INSUFFICIENT_INFO_MESSAGE, format_context_and_citation_map, generate_extractive_summary
from app.workspace import workspace_manager


@pytest.fixture(scope="module")
def user28_workspace():
    idx, ret = workspace_manager.get_user_workspace(28)
    assert len(idx.chunks) > 0, "User 28 must have indexed chunks"
    return idx, ret


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as client:
        yield client


# =====================================================================
# EMPLOYEE DATABASE TESTS (Questions 1 - 7)
# =====================================================================

def test_emp001_equivalent_questions_retrieve_consistent_profile(user28_workspace):
    """Verify that equivalent questions retrieve the complete profile of EMP001 as a clean Markdown table."""
    _, ret = user28_workspace

    equivalent_questions = [
        "Show me the history of EMP001.",
        "History of EMP001.",
        "EMP001 history.",
        "Tell me about EMP001.",
        "Give me the details of EMP001.",
        "What information is available about EMP001?",
        "Show EMP001’s complete profile.",
    ]

    answers = []
    citations_list = []

    for q in equivalent_questions:
        results = ret.retrieve(q, top_k=3)
        assert len(results) > 0, f"Retriever must find candidate chunks for {q}"
        _, cmap = format_context_and_citation_map(results)
        ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

        # Grounding & formatting assertions
        assert ans != INSUFFICIENT_INFO_MESSAGE, f"Expected profile for {q}, got insufficient info"
        assert len(cits) >= 1, f"Expected citation for {q}"
        assert cits[0].source == "Employee_Database_100_Employees.pdf"
        assert cits[0].page == 1

        # Table structure assertions
        assert "| Field | Details |" in ans or "| :--- | :--- |" in ans
        assert "EMP001" in ans
        assert "Aman Aggarwal" in ans
        assert "Finance" in ans
        assert "Accountant" in ans
        assert "4 years" in ans
        assert "Accounting, GST, Tally" in ans

        answers.append(ans)
        citations_list.append(cits)

    # Verify consistency across all equivalent formulations
    first_ans_cleaned = re.sub(r"\[\d+\]", "", answers[0]).strip()
    for i, a in enumerate(answers[1:], start=2):
        a_cleaned = re.sub(r"\[\d+\]", "", a).strip()
        assert a_cleaned == first_ans_cleaned, f"Question formulation {i} diverged from canonical profile format"


def test_what_is_the_experience_of_emp001(user28_workspace):
    """Verify that specific field inquiry retrieves accurate numerical value with citation."""
    _, ret = user28_workspace
    q = "What is the experience of EMP001?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "4 years" in ans
    assert "Aman Aggarwal" in ans or "EMP001" in ans
    assert len(cits) >= 1
    assert cits[0].source == "Employee_Database_100_Employees.pdf"
    assert cits[0].page == 1


def test_compare_emp001_and_emp025(user28_workspace):
    """Verify that comparison question formats answers as a comparison table."""
    _, ret = user28_workspace
    q = "Compare EMP001 and EMP025."
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "| Field | EMP001 | EMP025 |" in ans
    assert "Aman Aggarwal" in ans
    assert "Chirag Saini" in ans
    assert len(cits) >= 2
    sources = {c.source for c in cits}
    assert "Employee_Database_100_Employees.pdf" in sources
    pages = {c.page for c in cits}
    assert 1 in pages and 2 in pages


def test_who_has_the_highest_experience(user28_workspace):
    """Verify that ranking extremum accurately sorts and identifies Rohan Rao (EMP070) with 18 years."""
    _, ret = user28_workspace
    q = "Who has the highest experience?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "Rohan Rao" in ans
    assert "EMP070" in ans
    assert "18 years" in ans
    assert len(cits) >= 1
    assert cits[0].source == "Employee_Database_100_Employees.pdf"
    assert cits[0].page == 4


def test_show_the_top_10_employees_by_projects_completed(user28_workspace):
    """Verify that multi-record ranking sorts data descending and outputs a 10-row ranked table."""
    _, ret = user28_workspace
    q = "Show the top 10 employees by projects completed."
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "| Rank | Employee ID | Name | Department | Projects Completed | Experience |" in ans

    # Top employee is Rahul Shinde (EMP051) with 43 projects
    assert "EMP051" in ans
    assert "Rahul Shinde" in ans
    assert "43" in ans

    # Verify 10 data rows in table
    table_rows = [line for line in ans.splitlines() if line.startswith("|") and not line.startswith("| Rank") and not line.startswith("| :---")]
    assert len(table_rows) == 10, f"Expected 10 ranked employee rows, got {len(table_rows)}"


# =====================================================================
# GENERAL DOCUMENT TESTS (Questions 1 - 5)
# =====================================================================

def test_paragraph_explained_question(user28_workspace):
    """Verify that conceptual question is presented as readable paragraphs with page citation."""
    _, ret = user28_workspace
    q = "What is Machine Learning?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    # Should not be forced into a table
    assert not ans.startswith("| Field |")
    assert "science" in ans.lower() or "programming computers" in ans.lower() or "learn from data" in ans.lower()
    cited_pages = [c.page for c in cits if c.page is not None]
    assert 32 in cited_pages or 749 in cited_pages


def test_table_answer_from_presentation_document(user28_workspace):
    """Verify that questions targeting table/structured data in presentation slides retrieve accurately."""
    _, ret = user28_workspace
    q = "What is the meaning of Experiment in basic concepts of probability?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "uncertain" in ans.lower() or "action" in ans.lower() or "die" in ans.lower()
    assert len(cits) >= 1
    assert any(c.source == "APTITUDE PPT R.pdf" for c in cits)


def test_summary_of_document_section(user28_workspace):
    """Verify that section summary request produces a concise structured summary with citations."""
    _, ret = user28_workspace
    q = "Provide a summary of Machine Learning basics."
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert len(cits) >= 1


def test_comparison_using_document_concepts(user28_workspace):
    """Verify that comparison across document concepts formats into a comparison table."""
    _, ret = user28_workspace
    q = "Compare supervised and unsupervised learning."
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans != INSUFFICIENT_INFO_MESSAGE
    assert "| Aspect |" in ans or "| Feature |" in ans or "Supervised" in ans
    assert "Unsupervised" in ans
    assert len(cits) >= 1


def test_unanswerable_question_rejected(user28_workspace):
    """Verify that questions not contained in uploaded documents are strictly rejected."""
    _, ret = user28_workspace
    q = "What is the secret recipe of Coca-Cola and Martian rocket fuel?"
    results = ret.retrieve(q, top_k=3)
    _, cmap = format_context_and_citation_map(results)
    ans, cits = generate_extractive_summary(results, cmap, query=q, user_id=28)

    assert ans == INSUFFICIENT_INFO_MESSAGE
    assert len(cits) == 0


# =====================================================================
# END-TO-END FASTAPI HTTP CLIENT TEST
# =====================================================================

def test_api_chat_endpoint_e2e(api_client):
    """Verify full HTTP API authentication and chat pipeline with dynamic answer generation."""
    # Register & Login user
    email = f"emp_tester_{id(object())}@corp.in"
    reg = api_client.post("/auth/register", json={"email": email, "password": "Password123!", "full_name": "Test User"})
    assert reg.status_code == 201

    login_resp = api_client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload Employee Database PDF
    pdf_path = "data/users/28/uploads/Employee_Database_100_Employees.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    up = api_client.post(
        "/documents/upload",
        files={"file": ("Employee_Database_100_Employees.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201

    # Create Conversation
    conv = api_client.post("/chat/conversations", json={"title": "EMP Test Chat"}, headers=headers)
    assert conv.status_code == 201
    conv_id = conv.json()["id"]

    # Send Question: Show me the history of EMP001.
    msg_resp = api_client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "Show me the history of EMP001.", "top_k": 3},
        headers=headers,
    )
    assert msg_resp.status_code == 200
    data = msg_resp.json()
    assert "| Field | Details |" in data["answer"]
    assert "Aman Aggarwal" in data["answer"]
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["source"] == "Employee_Database_100_Employees.pdf"
    assert data["citations"][0]["page"] == 1
