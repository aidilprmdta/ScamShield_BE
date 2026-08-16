"""Heuristik URL: expand redirect + deteksi IP / '-' berlebih pada domain."""
import re
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_IPV4_RE = re.compile(r"(?:^|\.)(\d{1,3}(?:\.\d{1,3}){3})$")
_HYPHEN_THRESHOLD = 3


def _domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower().split(":")[0]


async def expand_short_link(url: str) -> str:
    """Follow redirect via httpx. Return URL asal jika gagal."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
        ) as client:
            resp = await client.head(url)
            if resp.status_code >= 400:
                resp = await client.get(url)
            return str(resp.url)
    except httpx.HTTPError as exc:
        logger.warning("Gagal expand %s: %s", url, exc)
        return url


def check_heuristics(url: str) -> dict:
    """Deteksi domain IP atau terlalu banyak '-'."""
    domain = _domain(url)
    flags: list[str] = []
    is_ip = bool(_IPV4_RE.search(domain.removeprefix("www.")))
    excessive_hyphens = domain.count("-") >= _HYPHEN_THRESHOLD

    if is_ip:
        flags.append("Domain berupa alamat IP mentah, bukan nama domain wajar")
    if excessive_hyphens:
        flags.append("Domain mengandung banyak tanda hubung, pola umum domain phishing")

    return {
        "domain": domain,
        "flags": flags,
        "is_ip": is_ip,
        "excessive_hyphens": excessive_hyphens,
    }
