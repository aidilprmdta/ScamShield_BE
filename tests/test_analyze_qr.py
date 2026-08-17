from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_QR_SAFE_RESULT = {
    "risk_score": 10,
    "risk_level": "low",
    "explanation": "Konten QR code adalah tautan atau teks resmi yang tidak menunjukkan indikasi bahaya.",
    "red_flags": [],
    "recommendation": "ignore",
    "recommendation_text": "QR code aman digunakan.",
    "category": None,
}

MOCK_QR_HIGH_RISK_RESULT = {
    "risk_score": 90,
    "risk_level": "high",
    "explanation": "QR code mengarahkan ke halaman login palsu untuk mencuri kredensial perbankan.",
    "red_flags": [
        {"label": "Phishing QRIS / Link", "detail": "Domain meniru portal resmi bank."}
    ],
    "recommendation": "block",
    "recommendation_text": "Jangan lanjutkan pembayaran atau membuka tautan ini.",
    "category": "QRIS Palsu",
}


@patch("app.api.v1.endpoints.analyze_qr.analyze_with_gemini", new_callable=AsyncMock)
def test_analyze_qr_text_data(mock_gemini):
    mock_gemini.return_value = MOCK_QR_HIGH_RISK_RESULT

    response = client.post(
        "/api/v1/analyze/qr",
        json={"decoded_content": "00020101021226590014ID.LINKAJA.WWW01189360091800000000015204581253033605802ID5913TOKO PALSU ABC"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["type"] == "qr"
    assert body["data"]["risk_level"] == "high"
    assert body["data"]["risk_score"] == 90
    mock_gemini.assert_awaited_once()


@patch("app.api.v1.endpoints.analyze_qr.analyze_gemini", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_qr.check_urlhaus", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.analyze_qr.check_heuristics")
@patch("app.api.v1.endpoints.analyze_qr.expand_short_link", new_callable=AsyncMock)
def test_analyze_qr_url_content(mock_expand, mock_heuristics, mock_urlhaus, mock_gemini):
    mock_expand.return_value = "https://safe-domain.com/pay"
    mock_heuristics.return_value = {"flags": [], "domain": "safe-domain.com"}
    mock_urlhaus.return_value = False
    mock_gemini.return_value = {
        "riskScore": 10,
        "riskLevel": "low",
        "explanation": "Tautan aman.",
        "recommendation": "Aman.",
    }

    response = client.post(
        "/api/v1/analyze/qr",
        json={"decoded_content": "https://safe-domain.com/pay"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["type"] == "qr"
    assert body["data"]["risk_level"] == "low"
    assert body["data"]["risk_score"] == 10
