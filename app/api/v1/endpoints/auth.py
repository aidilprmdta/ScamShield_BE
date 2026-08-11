from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, Depends

from app.core.config import get_settings
from app.models.auth_schema import (
    AuthMeData,
    AuthMeResponse,
    AuthResponse,
    AuthTokens,
    GoogleLoginRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.utils.exceptions import UnauthorizedError, ValidationAppError

import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import Request

router = APIRouter()


def _parse_identity_toolkit_error(payload: Any) -> str:
    """
    Format umum error Identity Toolkit:
    {
      "error": {
        "message": "INVALID_PASSWORD",
        "code": 400,
        "errors": [...]
      }
    }
    """
    try:
        return payload.get("error", {}).get("message", "UNKNOWN_ERROR")
    except Exception:  # noqa: BLE001
        return "UNKNOWN_ERROR"


def _map_error_message_to_http_status(message: str) -> None:
    """
    Melempar AppError yang sudah punya handler global.
    """
    msg = (message or "").upper()

    if msg in {"EMAIL_EXISTS"}:
        raise ValidationAppError("Email sudah terdaftar.")

    if msg in {"INVALID_EMAIL"}:
        raise ValidationAppError("Email tidak valid.")

    if msg in {"WEAK_PASSWORD"}:
        raise ValidationAppError("Password terlalu lemah. Minimal 6 karakter.")

    # Login errors
    if msg in {"INVALID_LOGIN_CREDENTIALS", "INVALID_PASSWORD"}:
        raise UnauthorizedError("Email atau password salah.")

    if msg in {"EMAIL_NOT_FOUND"}:
        raise UnauthorizedError("Email tidak ditemukan.")

    if msg in {"USER_DISABLED"}:
        raise UnauthorizedError("User dinonaktifkan.")

    if msg in {"OPERATION_NOT_ALLOWED"}:
        raise ValidationAppError(
            "Metode login belum diaktifkan di Firebase. Aktifkan Email/Password atau Google di Firebase Console."
        )

    if msg in {"INVALID_IDP_RESPONSE", "INVALID_ID_TOKEN", "CREDENTIAL_TOO_OLD_LOGIN_AGAIN"}:
        raise ValidationAppError("Token Google tidak valid atau kedaluwarsa. Silakan coba lagi.")

    if msg in {"CONFIGURATION_NOT_FOUND", "PROJECT_PUBLIC_ID_NOT_FOUND"}:
        raise ValidationAppError(
            "Firebase Authentication belum diaktifkan. Buka Firebase Console project "
            "'scamshield-ai-2026' > Authentication > Get Started, lalu aktifkan "
            "Email/Password dan Google Sign-In."
        )

    # Fallback
    raise ValidationAppError(f"Login/Register gagal: {message}")


@router.post("/auth/register", response_model=AuthResponse, summary="Register pengguna (Firebase email/password)")
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest) -> AuthResponse:
    settings = get_settings()

    if not settings.firebase_web_api_key:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
        f"?key={settings.firebase_web_api_key}"
    )

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.post(
            url,
            json={
                "email": payload.email,
                "password": payload.password,
                "returnSecureToken": True,
            },
        )

    if resp.status_code != 200:
        data = resp.json() if resp.content else {}
        message = _parse_identity_toolkit_error(data)
        _map_error_message_to_http_status(message)

    body = resp.json()
    tokens = AuthTokens(
        idToken=body["idToken"],
        refreshToken=body["refreshToken"],
        localId=body["localId"],
        email=body.get("email"),
    )
    return AuthResponse(data=tokens)


@router.post("/auth/login", response_model=AuthResponse, summary="Login pengguna (Firebase email/password)")
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest) -> AuthResponse:
    settings = get_settings()

    if not settings.firebase_web_api_key:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={settings.firebase_web_api_key}"
    )

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.post(
            url,
            json={
                "email": payload.email,
                "password": payload.password,
                "returnSecureToken": True,
            },
        )

    if resp.status_code != 200:
        data = resp.json() if resp.content else {}
        message = _parse_identity_toolkit_error(data)
        _map_error_message_to_http_status(message)

    body = resp.json()
    tokens = AuthTokens(
        idToken=body["idToken"],
        refreshToken=body["refreshToken"],
        localId=body["localId"],
        email=body.get("email"),
    )
    return AuthResponse(data=tokens)


@router.post("/auth/google", response_model=AuthResponse, summary="Login/Register via Google ID token")
async def google_login(payload: GoogleLoginRequest) -> AuthResponse:
    """
    Menerima Google ID token dari FE (dari Credential Manager / Google Sign-In),
    lalu menukarnya ke Firebase ID token via Identity Toolkit signInWithIdp.
    Jika user belum ada di Firebase Auth, otomatis di-create (register).
    """
    settings = get_settings()

    if not settings.firebase_web_api_key:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
        f"?key={settings.firebase_web_api_key}"
    )

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        encoded_token = quote(payload.id_token, safe="")
        resp = await client.post(
            url,
            json={
                "postBody": f"id_token={encoded_token}&providerId=google.com",
                "requestUri": "https://localhost",
                "returnIdpCredential": True,
                "returnSecureToken": True,
            },
        )

    if resp.status_code != 200:
        data = resp.json() if resp.content else {}
        message = _parse_identity_toolkit_error(data)
        _map_error_message_to_http_status(message)

    body = resp.json()
    tokens = AuthTokens(
        idToken=body["idToken"],
        refreshToken=body["refreshToken"],
        localId=body["localId"],
        email=body.get("email"),
    )
    return AuthResponse(data=tokens)


@router.post("/auth/refresh", response_model=AuthResponse, summary="Refresh ID token menggunakan refresh token")
@limiter.limit("20/minute")
async def refresh_token(request: Request, payload: RefreshTokenRequest) -> AuthResponse:
    settings = get_settings()

    if not settings.firebase_web_api_key:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    url = f"https://securetoken.googleapis.com/v1/token?key={settings.firebase_web_api_key}"

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        resp = await client.post(
            url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": payload.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        raise UnauthorizedError("Refresh token tidak valid atau kedaluwarsa.")

    body = resp.json()
    tokens = AuthTokens(
        idToken=body["id_token"],
        refreshToken=body["refresh_token"],
        localId=body["user_id"],
        email=None,
    )
    return AuthResponse(data=tokens)


@router.get("/auth/me", response_model=AuthMeResponse, summary="Ambil data user dari Firebase ID token")
async def me(
    user_id: str = Depends(get_current_user),
    authorization: Optional[str] = Header(default=None),
) -> AuthMeResponse:
    """
    Mengembalikan informasi minimal user dari Firebase ID token:
    - uid
    - email (jika tersedia di token)
    """
    # decode token lagi untuk ambil claims email (uid sudah ada via dependency)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    token = authorization.split(" ", 1)[1].strip()

    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001
        raise UnauthorizedError("Token tidak valid atau kedaluwarsa.") from exc

    return AuthMeResponse(
        data=AuthMeData(
            uid=user_id,
            email=decoded.get("email"),
            admin=bool(decoded.get("admin", False)),
        )
    )

