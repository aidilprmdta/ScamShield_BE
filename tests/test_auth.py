from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.security import decode_firebase_token
from app.main import app
from app.utils.exceptions import UnauthorizedError

client = TestClient(app)

MOCK_REGISTER_RESPONSE = {
    "idToken": "mock_id_token_123",
    "refreshToken": "mock_refresh_token_456",
    "localId": "user_abc",
    "email": "test@example.com",
}

MOCK_REFRESH_RESPONSE = {
    "id_token": "new_id_token_789",
    "refresh_token": "new_refresh_token_012",
    "user_id": "user_abc",
}


@patch("app.api.v1.endpoints.auth.httpx.AsyncClient")
def test_register_success(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_REGISTER_RESPONSE
    mock_response.content = b"ok"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["idToken"] == "mock_id_token_123"
    assert body["data"]["refreshToken"] == "mock_refresh_token_456"
    assert body["data"]["localId"] == "user_abc"


@patch("app.api.v1.endpoints.auth.httpx.AsyncClient")
def test_login_success(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_REGISTER_RESPONSE
    mock_response.content = b"ok"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["idToken"] == "mock_id_token_123"


@patch("app.api.v1.endpoints.auth.httpx.AsyncClient")
def test_login_invalid_credentials(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {"message": "INVALID_LOGIN_CREDENTIALS"}
    }
    mock_response.content = b"error"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "wrong"},
    )

    assert response.status_code in (401, 400, 422)


@patch("app.api.v1.endpoints.auth.httpx.AsyncClient")
def test_refresh_token_success(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_REFRESH_RESPONSE
    mock_response.content = b"ok"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "mock_refresh_token_456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["idToken"] == "new_id_token_789"
    assert body["data"]["refreshToken"] == "new_refresh_token_012"


def test_register_missing_password():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com"},
    )
    assert response.status_code == 422


def test_register_short_password():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "12345"},
    )
    assert response.status_code == 422


def test_me_without_token_returns_401():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_invalid_token_returns_401():
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").lower().startswith("bearer")


def test_decode_malformed_token_raises_unauthorized():
    try:
        decode_firebase_token("not-a-valid-jwt")
        assert False, "token rusak harus ditolak"
    except UnauthorizedError:
        pass


@patch("app.api.v1.endpoints.auth.httpx.AsyncClient")
def test_google_login_does_not_encode_jwt_dots(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_REGISTER_RESPONSE
    mock_response.content = b"ok"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    google_jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkifQ.signature"
    response = client.post("/api/v1/auth/google", json={"id_token": google_jwt})
    assert response.status_code == 200
    sent_json = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
    assert "id_token=eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkifQ.signature&providerId=google.com" in sent_json["postBody"]
    assert "%2E" not in sent_json["postBody"]
