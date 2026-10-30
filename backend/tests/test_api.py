from fastapi.testclient import TestClient
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
