"""
Cache in-memory sederhana (TTL + batas ukuran) untuk hasil analisis LLM atas
input yang identik — mitigasi risiko rate-limit/biaya membengkak (PRD §11):
"Retry dengan backoff, cache hasil analisis untuk input identik".

Catatan: ini cache per-proses (in-memory), cukup untuk skala MVP/lomba.
Untuk produksi multi-instance, ganti implementasi ini dengan Redis
(interface get/set di bawah sudah didesain agar mudah diswap).
"""
import hashlib
import time
from collections import OrderedDict
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_ENTRIES = 500
_store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()


def make_cache_key(*parts: str) -> str:
    raw = "||".join(p.strip().lower() for p in parts if p is not None)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _store.pop(key, None)
        return None
    # LRU touch
    _store.move_to_end(key)
    logger.info("Cache hit untuk key=%s...", key[:12])
    return value


def cache_set(key: str, value: Any) -> None:
    settings = get_settings()
    ttl = settings.analysis_cache_ttl_seconds
    _store[key] = (time.time() + ttl, value)
    _store.move_to_end(key)
    while len(_store) > _MAX_ENTRIES:
        _store.popitem(last=False)


def cache_clear() -> None:
    """Dipakai oleh test suite untuk memastikan isolasi antar test."""
    _store.clear()
