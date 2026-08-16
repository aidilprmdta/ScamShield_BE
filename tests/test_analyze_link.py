from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_GEMINI_SAFE = {
    "riskScore": 15,
    "riskLevel": "low",
    "explanation": "Tautan mengarah ke domain resmi dan tidak ditemukan indikasi berbahaya.",
    "recommendation": "Aman untuk dibuka.",
}


@patch("app.api.v1.endpoints.analyze_link.analyze_gemini", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_urlhaus", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_heuristics")
@patch("app.api.v1.endpoints.analyze_link.expand_short_link", new_callable=AsyncMock)
def test_analyze_link_safe(mock_expand, mock_heuristics, mock_urlhaus, mock_gemini):
    mock_expand.return_value = "https://example.com"
    mock_heuristics.return_value = {"flags": [], "domain": "example.com"}
    mock_urlhaus.return_value = False
    mock_gemini.return_value = MOCK_GEMINI_SAFE

    response = client.post("/api/v1/analyze/link", json={"url": "https://example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["risk_level"] == "low"
    assert body["data"]["risk_score"] == 15
    assert body["data"]["link_reputation"]["urlhaus_flagged"] is False
    mock_gemini.assert_awaited_once()


@patch("app.api.v1.endpoints.analyze_link.analyze_gemini", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_urlhaus", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_link.check_heuristics")
@patch("app.api.v1.endpoints.analyze_link.expand_short_link", new_callable=AsyncMock)
def test_analyze_link_urlhaus_hit_skips_gemini(
    mock_expand, mock_heuristics, mock_urlhaus, mock_gemini
):
    mock_expand.return_value = "https://phishing-bca-login.xyz"
    mock_heuristics.return_value = {
        "flags": ["Domain mengandung banyak tanda hubung, pola umum domain phishing"],
        "domain": "phishing-bca-login.xyz",
    }
    mock_urlhaus.return_value = True

    response = client.post(
        "/api/v1/analyze/link", json={"url": "http://phishing-bca-login.xyz"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["risk_level"] == "high"
    assert body["data"]["risk_score"] == 95
    assert body["data"]["link_reputation"]["urlhaus_flagged"] is True
    mock_gemini.assert_not_awaited()


def test_analyze_link_invalid_url_returns_422():
    response = client.post("/api/v1/analyze/link", json={"url": "bukan url sama sekali!!"})
    assert response.status_code == 422
