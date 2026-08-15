from fastapi.testclient import TestClient

from app.main import app
from app.repositories import firestore_repository as fr

client = TestClient(app)


def setup_function() -> None:
    fr._use_local_fallback = True


def test_education_list_loads_seed():
    response = client.get("/api/v1/education")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    first = body["data"][0]
    assert first["id"]
    assert first["title"]
    assert first["published_at"]
    assert "thumbnail_url" in first


def test_education_detail_quiz_normalizes_camel_case():
    response = client.get("/api/v1/education/kuis-kenali-modus-scam")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["type"] == "quiz"
    questions = data["quiz_questions"]
    assert questions
    assert "correct_index" in questions[0]
    assert isinstance(questions[0]["correct_index"], int)


def test_education_missing_returns_404():
    response = client.get("/api/v1/education/tidak-ada")
    assert response.status_code == 404
    assert response.json()["success"] is False
