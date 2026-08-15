"""
Verifikasi Firebase ID Token dari header Authorization: Bearer <token>.
Menerima token dari project Android (scamshieldai-9de2170b) maupun project lama.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Optional

import firebase_admin
from fastapi import Header
from firebase_admin import auth as firebase_auth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.exceptions import UnauthorizedError

logger = get_logger(__name__)

_CLOCK_SKEW_SECONDS = 60


def _allowed_projects() -> list[str]:
    settings = get_settings()
    raw = settings.firebase_project_ids or settings.firebase_project_id
    projects = [p.strip() for p in raw.split(",") if p.strip()]
    if not projects:
        projects = ["scamshieldai-9de2170b", "scamshield-ai-2026"]
    return projects


def _admin_project_id() -> Optional[str]:
    if not firebase_admin._apps:
        return None
    try:
        return firebase_admin.get_app().project_id
    except Exception:  # noqa: BLE001
        return None


def _peek_jwt_claims(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:  # noqa: BLE001
        return {}


def _issuer_ok(decoded: dict[str, Any], audience: str) -> bool:
    iss = decoded.get("iss")
    aud = decoded.get("aud") or audience
    if not isinstance(iss, str) or not aud:
        return False
    return iss == f"https://securetoken.google.com/{aud}"


def _verify_with_google(token: str, audience: str, request: google_requests.Request) -> Optional[dict[str, Any]]:
    try:
        decoded = google_id_token.verify_firebase_token(
            token,
            request,
            audience=audience,
            clock_skew_in_seconds=_CLOCK_SKEW_SECONDS,
        )
    except TypeError:
        decoded = google_id_token.verify_firebase_token(token, request, audience=audience)
    if not decoded:
        return None
    if not _issuer_ok(decoded, audience):
        return None
    return decoded


def decode_firebase_token(token: str) -> dict[str, Any]:
    """
    Verifikasi ID token Firebase.
    Admin SDK hanya valid untuk project service account; jika beda project,
    verifikasi lewat sertifikat Google dengan audience yang sesuai.
    """
    if not token or token.count(".") != 2:
        raise UnauthorizedError("Token tidak valid atau kedaluwarsa.")

    last_error: Exception | None = None
    allowed = _allowed_projects()
    claims = _peek_jwt_claims(token)
    aud = claims.get("aud") if isinstance(claims.get("aud"), str) else None
    admin_project = _admin_project_id()

    if firebase_admin._apps and (aud is None or aud == admin_project):
        try:
            return firebase_auth.verify_id_token(token, clock_skew_seconds=_CLOCK_SKEW_SECONDS)
        except TypeError:
            try:
                return firebase_auth.verify_id_token(token)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.info("Admin SDK menolak token: %s", exc)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.info("Admin SDK menolak token: %s", exc)

    audiences: list[str] = []
    if aud:
        audiences.append(aud)
    for project_id in allowed:
        if project_id not in audiences:
            audiences.append(project_id)

    request = google_requests.Request()
    for audience in audiences:
        try:
            decoded = _verify_with_google(token, audience, request)
            if not decoded:
                continue
            project = decoded.get("aud")
            if project in allowed or audience in allowed:
                return decoded
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    logger.warning("Gagal verifikasi Firebase ID token: %s", last_error)
    raise UnauthorizedError("Token tidak valid atau kedaluwarsa.") from last_error


def _uid_from_claims(decoded: dict[str, Any]) -> str:
    uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
    if not uid:
        raise UnauthorizedError("Token tidak valid atau kedaluwarsa.")
    return str(uid)


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Dependency WAJIB login: mengembalikan uid dari Firebase ID token.
    Melempar 401 jika token tidak ada / tidak valid.
    """
    token = _bearer_token(authorization)
    if not token:
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    decoded = decode_firebase_token(token)
    return _uid_from_claims(decoded)


async def get_admin_user(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Dependency WAJIB admin: verifikasi token + custom claim / daftar admin.
    """
    token = _bearer_token(authorization)
    if not token:
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    decoded = decode_firebase_token(token)
    uid = _uid_from_claims(decoded)
    if decoded.get("admin", False):
        return uid

    email = decoded.get("email")
    from app.repositories.firestore_repository import is_admin_user

    if is_admin_user(uid, email if isinstance(email, str) else None):
        return uid
    raise UnauthorizedError("Akses ditolak. Hanya admin yang bisa mengakses endpoint ini.")


async def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """
    Dependency OPSIONAL login: mengembalikan uid jika token valid,
    None jika tidak ada token (tamu).

    Jika header Bearer ada tetapi token invalid/kedaluwarsa, lempar 401
    supaya klien bisa refresh — jangan anggap sebagai tamu.
    """
    token = _bearer_token(authorization)
    if not token:
        return None
    decoded = decode_firebase_token(token)
    return _uid_from_claims(decoded)
