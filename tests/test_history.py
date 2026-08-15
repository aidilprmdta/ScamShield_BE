from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.models.analyze_schema import AnalysisResult, RecommendedAction, RiskLevel, ScanType
from app.repositories import firestore_repository as fr
from app.repositories import local_store

client = TestClient(app)


async def _user() -> str:
    return "user_history_1"


def setup_function() -> None:
    fr._use_local_fallback = True
    with local_store._LOCK:
        data = local_store._ensure_store()
        data["scan_history"] = {}
        local_store._write(data)


def test_history_requires_auth():
    response = client.get("/api/v1/history")
    assert response.status_code == 401
    assert response.json()["success"] is False


def test_history_returns_saved_scan():
    app.dependency_overrides[get_current_user] = _user
    try:
        result = AnalysisResult(
            type=ScanType.CHAT,
            input_summary="OTP palsu",
            risk_score=90,
            risk_level=RiskLevel.HIGH,
            explanation="phishing",
            recommendation=RecommendedAction.BLOCK,
            recommendation_text="Blokir",
            created_at="2026-08-14T00:00:00+00:00",
        )
        scan_id = local_store.save_scan_history("user_history_1", result.model_dump(mode="json"))
        response = client.get("/api/v1/history", headers={"Authorization": "Bearer x"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["scan_id"] == scan_id
        assert data[0]["risk_level"] == "high"
    finally:
        app.dependency_overrides.clear()
