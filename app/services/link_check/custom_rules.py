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


_KNOWN_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "s.id", "cutt.ly", "is.gd",
    "rb.gy", "shorturl.at", "linktr.ee", "ow.ly", "buff.ly", "goo.gl"
}

async def expand_short_link(url: str) -> str:
    """Follow redirect via httpx. Timeout singkat 2.5 detik agar tidak menunda analisis."""
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower().split(":")[0].removeprefix("www.")
    
    # Hanya expand jika berpotensi shortener atau memiliki path redirect
    is_likely_short = domain in _KNOWN_SHORTENERS or len(domain) <= 8
    timeout_sec = 2.5 if is_likely_short else 1.5

    try:
        async with httpx.AsyncClient(
            timeout=timeout_sec,
            follow_redirects=True,
        ) as client:
            resp = await client.head(url)
            if resp.status_code >= 400 and is_likely_short:
                resp = await client.get(url)
            return str(resp.url)
    except (httpx.HTTPError, Exception) as exc:
        logger.debug("Skip/gagal expand %s: %s", url, exc)
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
