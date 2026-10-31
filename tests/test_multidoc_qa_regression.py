import io
import time
import pytest
from pypdf import PdfReader, PdfWriter
from fastapi.testclient import TestClient

from app.main import app, INSUFFICIENT_INFO_MESSAGE
from app.auth import db, create_user_session
from app.workspace import workspace_manager


@pytest.fixture(scope="module")
def multi_doc_setup():
    """Create a fresh isolated user with two authentic extracted PDF documents."""
    client = TestClient(app)
    user_email = f"multidoc_reg_{int(time.time()*1000)}@example.com"
    user_pass = "MultiDocPass123!"

    # 1. Register user
    reg_resp = client.post("/auth/register", json={"email": user_email, "password": user_pass})
    assert reg_resp.status_code == 201, reg_resp.text
    user_data = reg_resp.json()
    user_id = user_data["id"]

    # 2. Login user
    login_resp = client.post("/auth/login", json={"email": user_email, "password": user_pass})
    assert login_resp.status_code == 200, login_resp.text
    tokens = login_resp.json()
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 3. Create two authentic test PDFs extracted from textbook pages
    source_pdf = "data/users/28/uploads/Hands-On_Machine_Learning_with_Scikit-Learn-Keras-and-TensorFlow-2nd-Edition-Aurelien-Geron.pdf"
    reader = PdfReader(source_pdf)

    # Doc A: Page 32 (Machine Learning definition by Arthur Samuel)
    writer_a = PdfWriter()
    writer_a.add_page(reader.pages[31])
    buf_a = io.BytesIO()
    writer_a.write(buf_a)
    buf_a.seek(0)
    pdf_a_bytes = buf_a.getvalue()

    # Doc B: Page 265 (Yann LeCun cake analogy of Unsupervised Learning)
    writer_b = PdfWriter()
    writer_b.add_page(reader.pages[264])
    buf_b = io.BytesIO()
    writer_b.write(buf_b)
    buf_b.seek(0)
    pdf_b_bytes = buf_b.getvalue()

    # Upload Doc A
    up_a = client.post(
        "/documents/upload",
        files={"file": ("Chapter1_Basics.pdf", pdf_a_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert up_a.status_code == 201, up_a.text
    doc_a_info = up_a.json()
    assert doc_a_info["chunk_count"] > 0

    # Upload Doc B
    up_b = client.post(
        "/documents/upload",
        files={"file": ("Chapter9_Unsupervised.pdf", pdf_b_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert up_b.status_code == 201, up_b.text
    doc_b_info = up_b.json()
    assert doc_b_info["chunk_count"] > 0

    # Initialize a chat conversation
    conv_resp = client.post(
        "/chat/conversations",
        json={"title": "Multi-Doc Test Conversation"},
        headers=auth_headers,
    )
    assert conv_resp.status_code == 201, conv_resp.text
    conv_id = conv_resp.json()["id"]

    return {
        "client": client,
        "headers": auth_headers,
        "user_id": user_id,
        "conv_id": conv_id,
        "doc_a": doc_a_info,
        "doc_b": doc_b_info,
    }


def test_chunk_counts_are_accurate_per_document(multi_doc_setup):
    """Verify that Doc B chunk count does not overwrite or accumulate onto Doc A."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]

    docs_resp = client.get("/documents", headers=headers)
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    assert len(docs) == 2

    doc_map = {d["filename"]: d["chunk_count"] for d in docs}
    assert "Chapter1_Basics.pdf" in doc_map
    assert "Chapter9_Unsupervised.pdf" in doc_map

    # Each individual document must have its true chunk count (2 chunks each), not 4
    assert doc_map["Chapter1_Basics.pdf"] == 2
    assert doc_map["Chapter9_Unsupervised.pdf"] == 2


def test_query_document_a_unique_fact(multi_doc_setup):
    """Verify that querying for Doc A's fact retrieves and cites Doc A."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]
    conv_id = multi_doc_setup["conv_id"]

    resp = client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "What is Machine Learning according to Arthur Samuel?", "top_k": 3},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["answer"] != INSUFFICIENT_INFO_MESSAGE
    assert len(data["citations"]) >= 1
    cited_sources = {c["source"] for c in data["citations"]}
    assert "Chapter1_Basics.pdf" in cited_sources
    assert any("field of study" in data["answer"].lower() or "programming computers" in data["answer"].lower() or "learn from data" in data["answer"].lower() for c in data["citations"])


def test_query_document_b_unique_fact(multi_doc_setup):
    """Verify that querying for Doc B's fact retrieves and cites Doc B, not failing after uploading second PDF."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]
    conv_id = multi_doc_setup["conv_id"]

    resp = client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "What did Yann LeCun say about unsupervised learning and cake?", "top_k": 3},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["answer"] != INSUFFICIENT_INFO_MESSAGE
    assert len(data["citations"]) >= 1
    cited_sources = {c["source"] for c in data["citations"]}
    assert "Chapter9_Unsupervised.pdf" in cited_sources
    assert "cake" in data["answer"].lower() or "icing" in data["answer"].lower()


def test_query_joint_multi_document_synthesis(multi_doc_setup):
    """Verify that cross-document question retrieves and cites both Document A and Document B."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]
    conv_id = multi_doc_setup["conv_id"]

    resp = client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "Explain machine learning and Yann LeCun cake analogy of unsupervised learning.", "top_k": 4},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["answer"] != INSUFFICIENT_INFO_MESSAGE
    cited_sources = {c["source"] for c in data["citations"]}
    assert "Chapter1_Basics.pdf" in cited_sources, f"Expected Chapter1_Basics.pdf in {cited_sources}"
    assert "Chapter9_Unsupervised.pdf" in cited_sources, f"Expected Chapter9_Unsupervised.pdf in {cited_sources}"


def test_query_unanswerable_question_returns_insufficient_info(multi_doc_setup):
    """Verify that question with facts absent from both documents returns INSUFFICIENT_INFO_MESSAGE."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]
    conv_id = multi_doc_setup["conv_id"]

    resp = client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "What is the optimal temperature for growing organic strawberries on Mars?", "top_k": 3},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["answer"] == INSUFFICIENT_INFO_MESSAGE
    assert len(data["citations"]) == 0
    assert data["generation_type"] == "insufficient_information"


def test_upload_scanned_pdf_records_zero_chunks_and_warns(multi_doc_setup):
    """Verify that uploading a scanned PDF (zero text stream) records 0 chunks, provides warning, and does not corrupt existing workspace."""
    client = multi_doc_setup["client"]
    headers = multi_doc_setup["headers"]
    conv_id = multi_doc_setup["conv_id"]

    # Use existing scanned PDF bytes
    scanned_path = "data/users/28/uploads/module 1 (DAA).pdf"
    with open(scanned_path, "rb") as f:
        scanned_bytes = f.read()

    up_scanned = client.post(
        "/documents/upload",
        files={"file": ("Scanned_Module_1.pdf", scanned_bytes, "application/pdf")},
        headers=headers,
    )
    assert up_scanned.status_code == 201, up_scanned.text
    scanned_info = up_scanned.json()

    # Must accurately report 0 chunks
    assert scanned_info["chunk_count"] == 0
    assert "warning" in scanned_info
    assert "No extractable text" in scanned_info["warning"]

    # Existing documents still queryable
    resp = client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={"message": "What is Machine Learning according to Arthur Samuel?", "top_k": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["answer"] != INSUFFICIENT_INFO_MESSAGE
