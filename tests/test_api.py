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
