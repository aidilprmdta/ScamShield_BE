from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

client = TestClient(app)


async def _user() -> str:
    return "uid_change_pwd"


def test_change_password_success():
    app.dependency_overrides[get_current_user] = _user

    mock_user = MagicMock()
    mock_user.email = "user@example.com"
    mock_user.provider_data = [MagicMock(provider_id="password")]

    sign_in_resp = MagicMock()
    sign_in_resp.status_code = 200
    sign_in_resp.json.return_value = {
        "idToken": "old-id-token",
        "refreshToken": "old-refresh",
        "localId": "uid_change_pwd",
        "email": "user@example.com",
    }

    update_resp = MagicMock()
    update_resp.status_code = 200
    update_resp.json.return_value = {
        "idToken": "new-id-token",
        "refreshToken": "new-refresh",
        "localId": "uid_change_pwd",
        "email": "user@example.com",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(side_effect=[sign_in_resp, update_resp])

    try:
        with patch("app.api.v1.endpoints.auth.firebase_auth.get_user", return_value=mock_user):
            with patch("app.api.v1.endpoints.auth.httpx.AsyncClient", return_value=mock_client):
                with patch("app.api.v1.endpoints.auth.get_settings") as mock_settings:
                    mock_settings.return_value.firebase_web_api_key = "test-key"
                    mock_settings.return_value.http_timeout_seconds = 10
                    response = client.post(
                        "/api/v1/auth/change-password",
                        json={
                            "current_password": "oldpass1",
                            "new_password": "newpass1",
                        },
                        headers={"Authorization": "Bearer token"},
                    )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["idToken"] == "new-id-token"
    assert body["data"]["refreshToken"] == "new-refresh"


def test_change_password_google_only_rejected():
    app.dependency_overrides[get_current_user] = _user

    mock_user = MagicMock()
    mock_user.email = "google@example.com"
    mock_user.provider_data = [MagicMock(provider_id="google.com")]

    try:
        with patch("app.api.v1.endpoints.auth.firebase_auth.get_user", return_value=mock_user):
            with patch("app.api.v1.endpoints.auth.get_settings") as mock_settings:
                mock_settings.return_value.firebase_web_api_key = "test-key"
                response = client.post(
                    "/api/v1/auth/change-password",
                    json={
                        "current_password": "anything",
                        "new_password": "newpass1",
                    },
                    headers={"Authorization": "Bearer token"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "Google" in response.json()["error"]["message"]
