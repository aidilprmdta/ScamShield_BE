"""
Fungsi validasi & normalisasi input yang dipakai lintas endpoint.
"""
import re
from urllib.parse import urlparse

from app.utils.exceptions import ValidationAppError

MAX_CHAT_TEXT_LENGTH = 8000
MIN_OCR_CONFIDENCE = 0.4

_URL_REGEX = re.compile(
    r"^(https?://)?"
    r"("
    r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"  # domain biasa
    r"|"
    r"\d{1,3}(\.\d{1,3}){3}"  # IPv4 mentah
    r")"
    r"(:\d+)?"
    r"(/[^\s]*)?$"
)


def validate_chat_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ValidationAppError("Teks chat tidak boleh kosong.")
    if len(text) > MAX_CHAT_TEXT_LENGTH:
        raise ValidationAppError(
            f"Teks chat terlalu panjang (maks {MAX_CHAT_TEXT_LENGTH} karakter)."
        )
    return text


def normalize_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise ValidationAppError("URL tidak boleh kosong.")

    if not _URL_REGEX.match(raw_url):
        raise ValidationAppError("Format URL tidak valid.")

    if not raw_url.lower().startswith(("http://", "https://")):
        raw_url = f"http://{raw_url}"

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        raise ValidationAppError("Format URL tidak valid.")

    return raw_url


def looks_like_url(text: str) -> bool:
    """Deteksi cepat apakah suatu string kemungkinan URL (dipakai oleh endpoint QR)."""
    candidate = (text or "").strip()
    if not candidate:
        return False
    return bool(_URL_REGEX.match(candidate)) or candidate.lower().startswith(
        ("http://", "https://", "www.")
    )
