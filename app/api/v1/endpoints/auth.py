from typing import Any, Optional

import httpx
from fastapi import APIRouter, Header, Depends

from app.core.config import get_settings
from app.models.auth_schema import (
    AuthMeData,
    AuthMeResponse,
    AuthResponse,
    AuthTokens,
    ChangePasswordRequest,
    ChangePasswordResponse,
    GoogleLoginRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UpdateProfileResponse,
)
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.core.security import decode_firebase_token, get_current_user
from app.repositories.firestore_repository import is_admin_user
from app.utils.exceptions import UnauthorizedError, ValidationAppError

from firebase_admin import auth as firebase_auth
from fastapi import Request

router = APIRouter()
logger = get_logger(__name__)


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
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            return str(error.get("message") or "UNKNOWN_ERROR")
        if isinstance(error, str) and error.strip():
            return error
        return "UNKNOWN_ERROR"
    except Exception:  # noqa: BLE001
        return "UNKNOWN_ERROR"


def _normalize_firebase_code(message: str) -> str:
    msg = (message or "").upper().strip()
    if ":" in msg:
        msg = msg.split(":", 1)[0].strip()
    return msg


def _map_error_message_to_http_status(message: str) -> None:
    """
    Melempar AppError yang sudah punya handler global.
    """
    raw = message or "UNKNOWN_ERROR"
    msg = _normalize_firebase_code(raw)

    if msg in {"EMAIL_EXISTS"}:
        raise ValidationAppError("Email sudah terdaftar.")

    if msg in {"INVALID_EMAIL"}:
        raise ValidationAppError("Email tidak valid.")

    if msg in {"WEAK_PASSWORD"}:
        raise ValidationAppError("Password terlalu lemah. Minimal 6 karakter.")

    if msg in {"INVALID_LOGIN_CREDENTIALS", "INVALID_PASSWORD", "EMAIL_NOT_FOUND"}:
        raise UnauthorizedError("Email atau password salah.")

    if msg in {"USER_DISABLED"}:
        raise UnauthorizedError("User dinonaktifkan.")

    if msg in {"OPERATION_NOT_ALLOWED", "PASSWORD_LOGIN_DISABLED"}:
        raise ValidationAppError(
            "Metode login belum diaktifkan di Firebase Authentication. "
            "Buka Console project 'scamshieldai-9de2170b' > Authentication > "
            "Sign-in method, lalu aktifkan Email/Password dan Google."
        )

    if msg in {"INVALID_IDP_RESPONSE", "INVALID_ID_TOKEN", "CREDENTIAL_TOO_OLD_LOGIN_AGAIN"}:
        raise ValidationAppError("Token Google tidak valid atau kedaluwarsa. Silakan coba lagi.")

    if msg in {"CONFIGURATION_NOT_FOUND", "PROJECT_PUBLIC_ID_NOT_FOUND"}:
        raise ValidationAppError(
            "Firebase Authentication belum diaktifkan. Buka Firebase Console project "
            "'scamshieldai-9de2170b' > Authentication > Get Started, lalu aktifkan "
            "Email/Password dan Google Sign-In."
        )

    if "API KEY" in raw.upper() or msg in {"API_KEY_INVALID", "API_KEY_NOT_VALID"}:
        raise ValidationAppError(
            "API key Firebase backend tidak valid. Gunakan Web API Key dari "
            "Firebase Console > Project settings (bukan key yang di-restrict Android saja)."
        )

    if "BLOCKED" in raw.upper() or "PERMISSION_DENIED" in raw.upper():
        raise ValidationAppError(
            "API key Firebase menolak permintaan dari server. Di Google Cloud Console, "
            "hapus Application restriction Android pada Web API key, atau buat key baru tanpa restriction."
        )

    raise ValidationAppError(f"Login/Register gagal: {message}")


def _identity_toolkit_keys() -> list[str]:
    settings = get_settings()
    keys: list[str] = []
    for raw in (settings.firebase_web_api_key, settings.firebase_web_api_key_fallback):
        if not isinstance(raw, str):
            continue
        key = raw.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


_RETRY_NEXT_KEY = {
    "INVALID_LOGIN_CREDENTIALS",
    "INVALID_PASSWORD",
    "EMAIL_NOT_FOUND",
    "OPERATION_NOT_ALLOWED",
    "PASSWORD_LOGIN_DISABLED",
    "CONFIGURATION_NOT_FOUND",
    "PROJECT_PUBLIC_ID_NOT_FOUND",
    "API_KEY_INVALID",
    "INVALID_IDP_RESPONSE",
    "INVALID_ID_TOKEN",
}


async def _identity_toolkit_post(path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    keys = _identity_toolkit_keys()
    if not keys:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    settings = get_settings()
    timeout = max(settings.http_timeout_seconds, 20)
    last_message = "UNKNOWN_ERROR"

    async with httpx.AsyncClient(timeout=timeout) as client:
        for index, key in enumerate(keys):
            url = f"https://identitytoolkit.googleapis.com/v1/{path}?key={key}"
            resp = await client.post(url, json=json_body)
            if resp.status_code == 200:
                return resp.json()
            data = resp.json() if resp.content else {}
            last_message = _parse_identity_toolkit_error(data)
            code = _normalize_firebase_code(last_message)
            can_retry = index < len(keys) - 1 and (
                code in _RETRY_NEXT_KEY
                or "API KEY" in last_message.upper()
                or "BLOCKED" in last_message.upper()
            )
            logger.warning("Identity Toolkit %s key[%s] gagal: %s", path, index, last_message)
            if can_retry:
                continue
            _map_error_message_to_http_status(last_message)

    _map_error_message_to_http_status(last_message)
    raise ValidationAppError(f"Login/Register gagal: {last_message}")


def _tokens_from_identity_toolkit(body: dict[str, Any]) -> AuthTokens:
    id_token = body.get("idToken")
    refresh = body.get("refreshToken")
    local_id = body.get("localId")
    if not id_token or not refresh or not local_id:
        raise ValidationAppError("Respons autentikasi tidak lengkap. Silakan coba lagi.")
    return AuthTokens(
        idToken=id_token,
        refreshToken=refresh,
        localId=local_id,
        email=body.get("email"),
    )


@router.post("/auth/register", response_model=AuthResponse, summary="Register pengguna (Firebase email/password)")
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest) -> AuthResponse:
    body = await _identity_toolkit_post(
        "accounts:signUp",
        {
            "email": payload.email,
            "password": payload.password,
            "returnSecureToken": True,
        },
    )
    return AuthResponse(data=_tokens_from_identity_toolkit(body))


@router.post("/auth/login", response_model=AuthResponse, summary="Login pengguna (Firebase email/password)")
@limiter.limit("30/minute")
async def login(request: Request, payload: LoginRequest) -> AuthResponse:
    body = await _identity_toolkit_post(
        "accounts:signInWithPassword",
        {
            "email": payload.email,
            "password": payload.password,
            "returnSecureToken": True,
        },
    )
    return AuthResponse(data=_tokens_from_identity_toolkit(body))


@router.post("/auth/google", response_model=AuthResponse, summary="Login/Register via Google ID token")
async def google_login(payload: GoogleLoginRequest) -> AuthResponse:
    """
    Menerima Google ID token dari FE (dari Credential Manager / Google Sign-In),
    lalu menukarnya ke Firebase ID token via Identity Toolkit signInWithIdp.
    Jika user belum ada di Firebase Auth, otomatis di-create (register).
    """
    token = payload.id_token.strip()
    if token.count(".") != 2:
        raise ValidationAppError("Token Google tidak valid. Silakan coba lagi.")
    body = await _identity_toolkit_post(
        "accounts:signInWithIdp",
        {
            "postBody": f"id_token={token}&providerId=google.com",
            "requestUri": "https://localhost",
            "returnIdpCredential": True,
            "returnSecureToken": True,
        },
    )
    return AuthResponse(data=_tokens_from_identity_toolkit(body))


@router.post("/auth/refresh", response_model=AuthResponse, summary="Refresh ID token menggunakan refresh token")
@limiter.limit("20/minute")
async def refresh_token(request: Request, payload: RefreshTokenRequest) -> AuthResponse:
    keys = _identity_toolkit_keys()
    if not keys:
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    settings = get_settings()
    last_ok = False
    body: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=max(settings.http_timeout_seconds, 20)) as client:
        for key in keys:
            resp = await client.post(
                f"https://securetoken.googleapis.com/v1/token?key={key}",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": payload.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                body = resp.json()
                last_ok = True
                break

    if not last_ok:
        raise UnauthorizedError("Refresh token tidak valid atau kedaluwarsa.")

    id_token = body.get("id_token")
    refresh = body.get("refresh_token")
    user_id = body.get("user_id")
    if not id_token or not refresh or not user_id:
        raise UnauthorizedError("Refresh token tidak valid atau kedaluwarsa.")

    tokens = AuthTokens(
        idToken=id_token,
        refreshToken=refresh,
        localId=user_id,
        email=None,
    )
    return AuthResponse(data=tokens)


@router.get("/auth/me", response_model=AuthMeResponse, summary="Ambil data user dari Firebase ID token")
async def me(
    user_id: str = Depends(get_current_user),
    authorization: Optional[str] = Header(default=None),
) -> AuthMeResponse:
    """
    Mengembalikan informasi user:
    - uid
    - email
    - display_name
    - admin claim
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    token = authorization.split(" ", 1)[1].strip()
    decoded = decode_firebase_token(token)

    display_name = decoded.get("name")
    email = decoded.get("email")
    try:
        user_record = firebase_auth.get_user(user_id)
        display_name = user_record.display_name or display_name
        email = user_record.email or email
    except Exception:  # noqa: BLE001
        pass

    return AuthMeResponse(
        data=AuthMeData(
            uid=user_id,
            email=email,
            display_name=display_name,
            admin=bool(decoded.get("admin", False))
            or is_admin_user(user_id, email if isinstance(email, str) else None),
        )
    )


@router.patch("/auth/me", response_model=UpdateProfileResponse, summary="Perbarui profil pengguna")
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    payload: UpdateProfileRequest,
    user_id: str = Depends(get_current_user),
    authorization: Optional[str] = Header(default=None),
) -> UpdateProfileResponse:
    """
    Update display_name dan/atau email via Identity Toolkit (project yang sama dengan token).
    """
    display_name = payload.display_name.strip() if payload.display_name else None
    email = payload.email.strip().lower() if payload.email else None

    if display_name is None and email is None:
        raise ValidationAppError("Tidak ada data yang diubah. Isi nama atau email.")

    if display_name is not None and len(display_name) < 2:
        raise ValidationAppError("Nama minimal 2 karakter.")

    if email is not None and ("@" not in email or "." not in email.split("@")[-1]):
        raise ValidationAppError("Email tidak valid.")

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    update_body: dict[str, Any] = {"idToken": token, "returnSecureToken": True}
    if display_name is not None:
        update_body["displayName"] = display_name
    if email is not None:
        update_body["email"] = email

    try:
        body = await _identity_toolkit_post("accounts:update", update_body)
    except ValidationAppError:
        raise
    except Exception as exc:  # noqa: BLE001
        try:
            update_kwargs: dict[str, Any] = {}
            if display_name is not None:
                update_kwargs["display_name"] = display_name
            if email is not None:
                update_kwargs["email"] = email
            user_record = firebase_auth.update_user(user_id, **update_kwargs)
            claims = user_record.custom_claims or {}
            return UpdateProfileResponse(
                data=AuthMeData(
                    uid=user_record.uid,
                    email=user_record.email,
                    display_name=user_record.display_name,
                    admin=bool(claims.get("admin", False))
                    or is_admin_user(user_record.uid, user_record.email),
                )
            )
        except firebase_auth.EmailAlreadyExistsError as admin_exc:
            raise ValidationAppError("Email sudah digunakan akun lain.") from admin_exc
        except Exception as admin_exc:  # noqa: BLE001
            raise ValidationAppError(f"Gagal memperbarui profil: {exc}") from admin_exc

    result_email = body.get("email") or email
    result_name = body.get("displayName") or display_name
    admin = False
    new_token = body.get("idToken") or token
    try:
        decoded = decode_firebase_token(new_token)
        admin = bool(decoded.get("admin", False))
    except Exception:  # noqa: BLE001
        pass

    return UpdateProfileResponse(
        data=AuthMeData(
            uid=body.get("localId") or user_id,
            email=result_email,
            display_name=result_name,
            admin=admin or is_admin_user(user_id, result_email if isinstance(result_email, str) else None),
        )
    )


@router.post(
    "/auth/change-password",
    response_model=ChangePasswordResponse,
    summary="Ubah kata sandi pengguna (email/password)",
)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user_id: str = Depends(get_current_user),
    authorization: Optional[str] = Header(default=None),
) -> ChangePasswordResponse:
    """
    Alur Firebase Identity Toolkit:
    1. Pastikan akun punya provider password (bukan Google-only)
    2. Verifikasi kata sandi lama via signInWithPassword
    3. Update kata sandi via accounts:update
    """
    if not _identity_toolkit_keys():
        raise ValidationAppError("Server belum dikonfigurasi untuk Firebase Auth (FIREBASE_WEB_API_KEY).")

    new_password = payload.new_password.strip()
    current_password = payload.current_password
    if len(new_password) < 6:
        raise ValidationAppError("Kata sandi baru minimal 6 karakter.")
    if new_password == current_password:
        raise ValidationAppError("Kata sandi baru harus berbeda dari kata sandi saat ini.")

    email = ""
    providers: list[str] = []
    try:
        user_record = firebase_auth.get_user(user_id)
        email = (user_record.email or "").strip()
        providers = [p.provider_id for p in (user_record.provider_data or [])]
    except Exception:  # noqa: BLE001
        if authorization and authorization.lower().startswith("bearer "):
            decoded = decode_firebase_token(authorization.split(" ", 1)[1].strip())
            email = (decoded.get("email") or "").strip()
        if not email:
            raise UnauthorizedError("Pengguna tidak ditemukan.")

    if providers and "password" not in providers:
        raise ValidationAppError(
            "Akun ini masuk dengan Google. Kata sandi tidak dapat diubah di aplikasi. "
            "Kelola keamanan melalui akun Google Anda."
        )

    if not email:
        raise ValidationAppError("Email akun tidak ditemukan. Tidak dapat mengubah kata sandi.")

    try:
        sign_in_payload = await _identity_toolkit_post(
            "accounts:signInWithPassword",
            {
                "email": email,
                "password": current_password,
                "returnSecureToken": True,
            },
        )
    except UnauthorizedError as exc:
        raise UnauthorizedError("Kata sandi saat ini salah.") from exc
    id_token = sign_in_payload.get("idToken")
    if not id_token:
        raise ValidationAppError("Gagal memverifikasi kata sandi saat ini.")

    update_payload = await _identity_toolkit_post(
        "accounts:update",
        {
            "idToken": id_token,
            "password": new_password,
            "returnSecureToken": True,
        },
    )

    tokens = AuthTokens(
        idToken=update_payload.get("idToken") or id_token,
        refreshToken=update_payload.get("refreshToken") or sign_in_payload.get("refreshToken", ""),
        localId=update_payload.get("localId") or user_id,
        email=update_payload.get("email") or email,
    )
    if not tokens.refreshToken:
        raise ValidationAppError("Kata sandi diubah, tetapi token sesi tidak lengkap. Silakan login ulang.")

    return ChangePasswordResponse(data=tokens)
