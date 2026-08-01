"""
Heuristik custom untuk menambah lapisan deteksi di luar Safe Browsing
(mis. shortlink yang belum terindeks) — sesuai PRD §7 & §11.
"""
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

KNOWN_SHORTLINK_DOMAINS = {
    "bit.ly", "tinyurl.com", "s.id", "cutt.ly", "t.co", "is.gd",
    "shorturl.at", "rebrand.ly", "bl.ink", "tiny.cc",
}

# Domain resmi umum yang sering ditiru (typosquatting) di Indonesia
COMMONLY_IMPERSONATED_BRANDS = [
    "bca", "bri", "bni", "mandiri", "dana", "ovo", "gopay", "shopee",
    "tokopedia", "grab", "gojek", "linkaja", "pln", "bpjs", "pos-indonesia",
    "telkomsel", "indosat",
]

SUSPICIOUS_TLDS = {".xyz", ".top", ".click", ".gq", ".tk", ".ml", ".cf", ".buzz", ".rest"}


def _get_domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower().split(":")[0]


def _looks_like_typosquat(domain: str) -> str | None:
    """Deteksi kasar: brand resmi muncul di subdomain/domain tapi bukan domain resmi asli."""
    core = domain.replace("www.", "")
    parts = core.split(".")
    base = parts[0] if parts else core
    for brand in COMMONLY_IMPERSONATED_BRANDS:
        if brand in core and not core.endswith(f"{brand}.co.id") and not core.endswith(f"{brand}.com"):
            # brand disebut tapi bukan domain resmi brand tsb -> potensi peniruan
            if base != brand:
                return brand
    return None


async def expand_shortlink(url: str) -> str:
    """
    Ikuti redirect shortlink untuk mendapatkan URL tujuan asli.
    Mengembalikan URL asal apabila expand gagal (fail-safe, bukan fatal error).
    """
    domain = _get_domain(url)
    if domain not in KNOWN_SHORTLINK_DOMAINS:
        return url

    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, follow_redirects=True
        ) as client:
            resp = await client.head(url)
            return str(resp.url)
    except httpx.HTTPError as exc:
        logger.warning("Gagal expand shortlink %s: %s", url, exc)
        return url


def evaluate_custom_rules(original_url: str, resolved_url: str) -> list[str]:
    """Mengembalikan daftar label heuristik yang terpicu (dipakai sbg konteks tambahan ke LLM)."""
    flags: list[str] = []
    resolved_domain = _get_domain(resolved_url)
    original_domain = _get_domain(original_url)

    if original_domain in KNOWN_SHORTLINK_DOMAINS:
        flags.append(f"Tautan pemendek ({original_domain}) mengarah ke: {resolved_domain}")

    typosquat_brand = _looks_like_typosquat(resolved_domain)
    if typosquat_brand:
        flags.append(
            f"Domain menyebut nama brand '{typosquat_brand}' tetapi bukan domain resmi brand tersebut"
        )

    for tld in SUSPICIOUS_TLDS:
        if resolved_domain.endswith(tld):
            flags.append(f"Menggunakan TLD yang sering disalahgunakan untuk phishing ({tld})")
            break

    if re.search(r"\d{1,3}(\.\d{1,3}){3}", resolved_domain):
        flags.append("Domain berupa alamat IP mentah, bukan nama domain wajar")

    if resolved_domain.count("-") >= 3:
        flags.append("Domain mengandung banyak tanda hubung, pola umum domain phishing")

    return flags


async def run_link_heuristics(url: str) -> dict[str, Any]:
    resolved_url = await expand_shortlink(url)
    flags = evaluate_custom_rules(url, resolved_url)
    return {
        "resolved_url": resolved_url,
        "flags": flags,
    }
