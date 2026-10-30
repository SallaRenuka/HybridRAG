from datetime import datetime, timedelta, timezone
import io
import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password, verify_password
from app.database import Database
from app.main import app

client = TestClient(app)


def test_password_hashing():
    raw_pw = "SuperSecurePassword123!"
    h1 = hash_password(raw_pw)
    h2 = hash_password(raw_pw)

    assert h1.startswith("scrypt$16384$8$1$")
    assert h2.startswith("scrypt$16384$8$1$")
    # Different random salts must yield different hash outputs
    assert h1 != h2

    # Verification must succeed for correct password and fail for wrong password
    assert verify_password(raw_pw, h1) is True
    assert verify_password("WrongPassword!", h1) is False


def test_user_registration():
    email = f"user_reg_{datetime.now().timestamp()}@example.com"
    resp = client.post("/auth/register", json={"email": email, "password": "Password123!"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert "id" in data
    assert "password_hash" not in data  # Never expose password hash!


def test_duplicate_email_registration_fails():
    email = f"duplicate_{datetime.now().timestamp()}@example.com"
    resp1 = client.post("/auth/register", json={"email": email, "password": "Password123!"})
    assert resp1.status_code == 201

    resp2 = client.post("/auth/register", json={"email": email, "password": "Password123!"})
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_login_success_and_failure():
    email = f"login_test_{datetime.now().timestamp()}@example.com"
    client.post("/auth/register", json={"email": email, "password": "CorrectPassword123!"})

    # Successful login
    login_resp = client.post("/auth/login", json={"email": email, "password": "CorrectPassword123!"})
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Failed login: incorrect password
    wrong_pw_resp = client.post("/auth/login", json={"email": email, "password": "WrongPassword"})
    assert wrong_pw_resp.status_code == 401

    # Failed login: non-existent email
    non_existent_resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "AnyPassword"})
    assert non_existent_resp.status_code == 401


def test_unauthorized_endpoint_access():
    # Missing Authorization header
    assert client.get("/auth/me").status_code == 401
    assert client.get("/documents").status_code == 401
    assert client.get("/chat/conversations").status_code == 401

    # Invalid / garbage token
    headers = {"Authorization": "Bearer totally_fake_invalid_token"}
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_logout_and_revoked_token():
    email = f"logout_test_{datetime.now().timestamp()}@example.com"
    client.post("/auth/register", json={"email": email, "password": "Password123!"})
    token = client.post("/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works
    assert client.get("/auth/me", headers=headers).status_code == 200

    # Logout
    logout_resp = client.post("/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "logged_out"

    # Using the token after logout MUST fail with 401
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_user_isolation_documents():
    ts = datetime.now().timestamp()
    alice_email = f"alice_{ts}@example.com"
    bob_email = f"bob_{ts}@example.com"

    client.post("/auth/register", json={"email": alice_email, "password": "PasswordAlice123!"})
    client.post("/auth/register", json={"email": bob_email, "password": "PasswordBob123!"})

    alice_token = client.post("/auth/login", json={"email": alice_email, "password": "PasswordAlice123!"}).json()["access_token"]
    bob_token = client.post("/auth/login", json={"email": bob_email, "password": "PasswordBob123!"}).json()["access_token"]

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Alice uploads a private file
    file_content = b"Alice Confidential Internal Financial Report."
    upload_resp = client.post(
        "/documents/upload",
        files={"file": ("alice_financials.txt", io.BytesIO(file_content), "text/plain")},
        headers=alice_headers,
    )
    assert upload_resp.status_code == 201
    alice_doc_id = upload_resp.json()["document_id"]

    # Alice can view her own document
    alice_view = client.get(f"/documents/{alice_doc_id}", headers=alice_headers)
    assert alice_view.status_code == 200
    assert alice_view.json()["filename"] == "alice_financials.txt"

    # Bob attempts to view Alice's document: MUST BE REJECTED WITH 403 FORBIDDEN!
    bob_view = client.get(f"/documents/{alice_doc_id}", headers=bob_headers)
    assert bob_view.status_code == 403
    assert "Access denied" in bob_view.json()["detail"]

    # Alice's document list contains 1 file; Bob's document list is empty!
    alice_docs = client.get("/documents", headers=alice_headers).json()
    bob_docs = client.get("/documents", headers=bob_headers).json()
    assert len(alice_docs) == 1
    assert len(bob_docs) == 0


def test_user_isolation_chat_history():
    ts = datetime.now().timestamp()
    alice_email = f"alice_chat_{ts}@example.com"
    bob_email = f"bob_chat_{ts}@example.com"

    client.post("/auth/register", json={"email": alice_email, "password": "PasswordAlice123!"})
    client.post("/auth/register", json={"email": bob_email, "password": "PasswordBob123!"})

    alice_token = client.post("/auth/login", json={"email": alice_email, "password": "PasswordAlice123!"}).json()["access_token"]
    bob_token = client.post("/auth/login", json={"email": bob_email, "password": "PasswordBob123!"}).json()["access_token"]

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Alice creates a private conversation
    create_conv_resp = client.post(
        "/chat/conversations",
        json={"title": "Alice Private Project Planning"},
        headers=alice_headers,
    )
    assert create_conv_resp.status_code == 201
    alice_conv_id = create_conv_resp.json()["id"]

    # Alice can access her conversation
    assert client.get(f"/chat/conversations/{alice_conv_id}", headers=alice_headers).status_code == 200

    # Bob attempts to access Alice's conversation: MUST RETURN 403 FORBIDDEN!
    bob_view = client.get(f"/chat/conversations/{alice_conv_id}", headers=bob_headers)
    assert bob_view.status_code == 403
    assert "Access denied" in bob_view.json()["detail"]

    # Bob attempts to send a message to Alice's conversation: MUST RETURN 403 FORBIDDEN!
    bob_msg = client.post(
        f"/chat/conversations/{alice_conv_id}/messages",
        json={"message": "Infiltrating Alice conversation"},
        headers=bob_headers,
    )
    assert bob_msg.status_code == 403


def test_expired_token_rejected():
    from app.auth import db
    ts = datetime.now().timestamp()
    email = f"expired_{ts}@example.com"
    client.post("/auth/register", json={"email": email, "password": "Password123!"})
    token = client.post("/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]

    # Manually backdate the session expiration in SQLite to simulate expiry
    past_timestamp = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with db.get_connection() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (past_timestamp, token))

    # Using the expired token MUST fail with 401 Unauthorized
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"]
