from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app

client = TestClient(app)


async def _mock_current_user() -> str:
    return "user123"


@patch("app.api.v1.endpoints.notifications._get_db")
def test_register_fcm_token_success(mock_get_db):
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_get_db.return_value = mock_db
    mock_db.collection.return_value.document.return_value = mock_doc

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
    mock_doc.set.assert_called_once()


def test_register_fcm_token_missing_auth():
    response = client.post(
        "/api/v1/notifications/register-token",
        json={"fcm_token": "fcm_token_abc123"},
    )
    assert response.status_code == 401
