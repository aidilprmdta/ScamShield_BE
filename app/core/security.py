"""
Verifikasi Firebase ID Token dari header Authorization: Bearer <token>.

MVP: autentikasi bersifat "Should Have" (lihat PRD §6), sehingga endpoint
analisis tetap bisa dipakai tanpa login (userId opsional / anonim),
namun endpoint yang menyentuh data milik user (history, report) sebaiknya
diamankan menggunakan dependency `get_current_user`.
"""
from typing import Optional

import firebase_admin
from fastapi import Header, HTTPException, status
from firebase_admin import auth as firebase_auth

from app.core.logging import get_logger
from app.utils.exceptions import UnauthorizedError

logger = get_logger(__name__)


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Dependency WAJIB login: mengembalikan uid dari Firebase ID token.
    Melempar 401 jika token tidak ada / tidak valid.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Header Authorization Bearer <token> wajib disertakan.")

    token = authorization.split(" ", 1)[1].strip()

    if not firebase_admin._apps:
        # Firebase belum diinisialisasi (mis. saat testing tanpa kredensial)
        raise UnauthorizedError("Layanan autentikasi belum dikonfigurasi.")

    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as exc:  # noqa: BLE001 - berbagai error firebase-admin
        logger.warning("Gagal verifikasi Firebase ID token: %s", exc)
        raise UnauthorizedError("Token tidak valid atau kedaluwarsa.") from exc


async def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """
    Dependency OPSIONAL login: mengembalikan uid jika token valid,
    None jika tidak ada token (dipakai di endpoint analyze/* agar tetap
    bisa dipakai oleh pengguna anonim/tamu).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
