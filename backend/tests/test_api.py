from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app

def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}

def test_empty_and_unsupported_questions():
    c = TestClient(app)
    assert c.post("/api/ask", json={"question": ""}).status_code == 422
    r = c.post("/api/ask", json={"question": "What is the weather?"})
    assert r.status_code == 422
    assert "total revenue" in r.json()["detail"]


def test_upload_requires_a_csv_file():
    response = TestClient(app).post(
        "/api/upload",
        files={"file": ("notes.txt", b"not a csv", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Upload a CSV file."


def test_chat_contract_returns_structured_answer():
    response = TestClient(app).post(
        "/api/chat",
        json={"question": "What is the weather?"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()

def test_auth_persists_session_and_rejects_duplicate_email():
    client = TestClient(app)
    email = f"auth-{uuid4().hex}@example.com"
    password = "correct horse battery"
    registration = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Auth User", "role": "Analyst"})
    assert registration.status_code == 200
    assert "token" not in registration.json()

    duplicate = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Other", "role": "Analyst"})
    assert duplicate.status_code == 409

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert "insightiq_session" in login.cookies
    assert "HttpOnly" in login.headers["set-cookie"]
    assert client.get("/api/auth/me").json()["email"] == email

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
