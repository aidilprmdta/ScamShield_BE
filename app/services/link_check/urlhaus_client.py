"""URLhaus (abuse.ch) — True jika query_status == ok."""
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

URLHAUS_ENDPOINT = "https://urlhaus-api.abuse.ch/v1/url/"

URLHAUS_HIT_RESULT = {
    "riskScore": 95,
    "riskLevel": "high",
    "explanation": (
        "Tautan ditemukan di database ancaman URLhaus (abuse.ch). "
        "URL ini telah dilaporkan sebagai berbahaya."
    ),
    "recommendation": (
        "Jangan buka tautan ini. Blokir pengirim dan laporkan jika diterima dari orang tidak dikenal."
    ),
}


async def check_urlhaus(url: str) -> bool:
    """POST ke URLhaus. True jika query_status == 'ok'. Fail-open → False."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(URLHAUS_ENDPOINT, data={"url": url})
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("URLhaus gagal (%s): %s", url, exc)
        return False

    return str(data.get("query_status", "")).lower() == "ok"
