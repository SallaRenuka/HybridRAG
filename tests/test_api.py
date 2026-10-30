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
