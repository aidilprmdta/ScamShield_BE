from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

client = TestClient(app)


async def _mock_current_user() -> str:
    return "user123"


@patch("app.api.v1.endpoints.notifications.save_fcm_token")
def test_register_fcm_token_success(mock_save):
    app.dependency_overrides[get_current_user] = _mock_current_user
    try:
        response = client.post(
            "/api/v1/notifications/register-token",
            json={"fcm_token": "fcm_token_abc123"},
            headers={"Authorization": "Bearer valid_token"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    mock_save.assert_called_once_with("user123", "fcm_token_abc123")


def test_register_fcm_token_missing_auth():
    response = client.post(
        "/api/v1/notifications/register-token",
        json={"fcm_token": "fcm_token_abc123"},
    )
    assert response.status_code == 401
