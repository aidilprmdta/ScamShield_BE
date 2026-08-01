from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MOCK_LLM_RESULT = {
    "risk_score": 82,
    "risk_level": "high",
    "explanation": "Pesan meminta kode OTP dengan dalih verifikasi akun, ini pola phishing umum.",
    "red_flags": [
        {"label": "Meminta kode OTP", "detail": "Bank resmi tidak pernah meminta OTP via chat."}
    ],
    "recommendation": "block",
    "recommendation_text": "Blokir pengirim dan jangan bagikan kode OTP ke siapa pun.",
    "category": "Phishing",
}


@patch("app.api.v1.endpoints.analyze_chat.analyze_with_gemini", new_callable=AsyncMock)
def test_analyze_chat_high_risk(mock_gemini):
    mock_gemini.return_value = MOCK_LLM_RESULT

    response = client.post(
        "/api/v1/analyze/chat",
        json={"text": "Mohon segera masukkan kode OTP Anda untuk verifikasi akun BCA."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["risk_level"] == "high"
    assert body["data"]["risk_score"] == 82
    assert body["data"]["recommendation"] == "block"
    assert body["data"]["related_education_category"] == "Phishing"
    mock_gemini.assert_awaited_once()


def test_analyze_chat_empty_text_returns_422():
    response = client.post("/api/v1/analyze/chat", json={"text": "   "})
    assert response.status_code == 422
    assert response.json()["success"] is False


def test_analyze_chat_low_ocr_confidence_rejected():
    response = client.post(
        "/api/v1/analyze/chat",
        json={"text": "teks tidak jelas", "source": "screenshot_ocr", "ocr_confidence": 0.1},
    )
    assert response.status_code == 422
    assert "OCR" in response.json()["error"]["message"]
