from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_rejects_short_question():
    client = TestClient(app)
    response = client.post("/query", json={"question": "x"})
    assert response.status_code == 422


def test_query_unindexed_raises_400():
    from app.main import index
    # Ensure empty index
    original_chunks = index.chunks
    original_faiss = index.faiss_index
    try:
        index.chunks = []
        index.faiss_index = None
        client = TestClient(app)
        response = client.post("/query", json={"question": "What is HybridRAG?"})
        assert response.status_code == 400
        assert "No documents indexed yet" in response.json()["detail"]
    finally:
        index.chunks = original_chunks
        index.faiss_index = original_faiss


def test_dashboard_stats_and_document_lifecycle():
    import io
    from datetime import datetime
    client = TestClient(app)
    ts = datetime.now().timestamp()
    email = f"stats_test_{ts}@example.com"

    # Register & Login
    client.post("/auth/register", json={"email": email, "password": "Password123!"})
    login_res = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Initial stats should be 0
    stats_res = client.get("/dashboard/stats", headers=headers)
    assert stats_res.status_code == 200
    data = stats_res.json()
    assert data["total_documents"] == 0
    assert data["total_conversations"] == 0

    # Upload a document
    file_bytes = b"Machine learning models learn patterns from empirical training datasets."
    upload_res = client.post(
        "/documents/upload",
        files={"file": ("ml_notes.txt", io.BytesIO(file_bytes), "text/plain")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    # Verify file endpoint serves the document
    file_res = client.get(f"/documents/{doc_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.content == file_bytes

    # Create a conversation
    conv_res = client.post("/chat/conversations", json={"title": "ML Discussion"}, headers=headers)
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Stats should now reflect 1 document, 1 conversation
    updated_stats = client.get("/dashboard/stats", headers=headers).json()
    assert updated_stats["total_documents"] == 1
    assert updated_stats["total_conversations"] == 1
    assert len(updated_stats["recent_documents"]) == 1

    # Search endpoint
    search_res = client.post("/search", json={"query": "machine learning patterns", "top_k": 3}, headers=headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_results"] > 0
    assert search_data["results"][0]["source"] == "ml_notes.txt"

    # Delete conversation
    del_conv = client.delete(f"/chat/conversations/{conv_id}", headers=headers)
    assert del_conv.status_code == 200
    assert del_conv.json()["status"] == "deleted"

    # Delete document
    del_doc = client.delete(f"/documents/{doc_id}", headers=headers)
    assert del_doc.status_code == 200
    assert del_doc.json()["status"] == "deleted"

    # Verify document is gone
    assert client.get(f"/documents/{doc_id}", headers=headers).status_code == 404
    final_stats = client.get("/dashboard/stats", headers=headers).json()
    assert final_stats["total_documents"] == 0
