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
