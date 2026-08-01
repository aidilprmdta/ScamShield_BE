"""
Klien untuk Google Safe Browsing API (v4) — cek reputasi URL.
Dokumentasi: https://developers.google.com/safe-browsing/v4/lookup-api
"""
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.exceptions import UpstreamServiceError

logger = get_logger(__name__)

SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]


async def check_url_reputation(url: str) -> dict[str, Any]:
    """
    Mengembalikan dict:
    {
        "is_flagged": bool,
        "threat_types": list[str],
        "verdict": str  # ringkasan untuk dikirim ke prompt LLM
    }
    Jika API key belum dikonfigurasi atau terjadi error, fallback ke "tidak dapat diperiksa"
    (bukan exception fatal) — sesuai mitigasi PRD §11 (downtime handling).
    """
    settings = get_settings()
    if not settings.google_safe_browsing_api_key:
        logger.warning("GOOGLE_SAFE_BROWSING_API_KEY tidak dikonfigurasi — melewati pengecekan.")
        return {
            "is_flagged": False,
            "threat_types": [],
            "verdict": "Tidak dapat diperiksa (API key belum dikonfigurasi).",
        }

    payload = {
        "client": {"clientId": "scamshield-ai", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(
                SAFE_BROWSING_ENDPOINT,
                params={"key": settings.google_safe_browsing_api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Safe Browsing API error: %s", exc)
        # Fallback: jangan gagalkan seluruh request, teruskan sebagai "tidak dapat diperiksa"
        return {
            "is_flagged": False,
            "threat_types": [],
            "verdict": "Tidak dapat diperiksa saat ini (layanan Safe Browsing bermasalah).",
        }

    matches = data.get("matches", [])
    if not matches:
        return {
            "is_flagged": False,
            "threat_types": [],
            "verdict": "Aman — tidak ditemukan di basis data ancaman Google Safe Browsing.",
        }

    threat_types = sorted({m.get("threatType", "UNKNOWN") for m in matches})
    return {
        "is_flagged": True,
        "threat_types": threat_types,
        "verdict": f"BERBAHAYA — terdeteksi di Google Safe Browsing sebagai: {', '.join(threat_types)}.",
    }
