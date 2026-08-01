from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_LLM_RESULT_SAFE = {
    "risk_score": 15,
    "risk_level": "low",
    "explanation": "Tautan mengarah ke domain resmi dan tidak ditemukan indikasi berbahaya.",
    "red_flags": [],
    "recommendation": "ignore",
    "recommendation_text": "Aman untuk dibuka.",
    "category": None,
}


@patch("app.api.v1.endpoints.analyze_link.analyze_with_gemini", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_url_reputation", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.run_link_heuristics", new_callable=AsyncMock)
def test_analyze_link_safe(mock_heuristics, mock_reputation, mock_gemini):
    mock_heuristics.return_value = {"resolved_url": "https://example.com", "flags": []}
    mock_reputation.return_value = {
        "is_flagged": False,
        "threat_types": [],
        "verdict": "Aman — tidak ditemukan di basis data ancaman.",
    }
    mock_gemini.return_value = MOCK_LLM_RESULT_SAFE

    response = client.post("/api/v1/analyze/link", json={"url": "https://example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["risk_level"] == "low"
    assert body["data"]["link_reputation"]["safe_browsing_flagged"] is False


@patch("app.api.v1.endpoints.analyze_link.analyze_with_gemini", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_url_reputation", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.run_link_heuristics", new_callable=AsyncMock)
def test_analyze_link_flagged_by_safe_browsing_forces_high_risk(
    mock_heuristics, mock_reputation, mock_gemini
):
    mock_heuristics.return_value = {"resolved_url": "https://phishing-bca-login.xyz", "flags": [
        "Menggunakan TLD yang sering disalahgunakan untuk phishing (.xyz)"
    ]}
    mock_reputation.return_value = {
        "is_flagged": True,
        "threat_types": ["SOCIAL_ENGINEERING"],
        "verdict": "BERBAHAYA — terdeteksi di Google Safe Browsing.",
    }
    # LLM sengaja mengembalikan skor rendah untuk memastikan force_high_risk yang menang
    mock_gemini.return_value = {
        "risk_score": 20,
        "risk_level": "low",
        "explanation": "x",
        "recommendation": "ignore",
    }

    response = client.post(
        "/api/v1/analyze/link", json={"url": "http://phishing-bca-login.xyz"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["risk_level"] == "high"
    assert body["data"]["risk_score"] >= 85
    assert body["data"]["link_reputation"]["safe_browsing_flagged"] is True


def test_analyze_link_invalid_url_returns_422():
    response = client.post("/api/v1/analyze/link", json={"url": "bukan url sama sekali!!"})
    assert response.status_code == 422
