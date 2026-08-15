"""
Wrapper panggilan Gemini API untuk analisis konten & explanation.

Catatan versi model (lihat PRD §7): Gemini 1.5 sudah deprecated per 2026.
Gunakan model terbaru yang tersedia (default: env GEMINI_MODEL, mis. "gemini-flash-latest").
Cek https://ai.google.dev/gemini-api/docs/models untuk model string terkini.
"""
import json
import re
from typing import Any

import google.generativeai as genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.cache import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai_engine.prompt_templates import SYSTEM_INSTRUCTION
from app.utils.exceptions import UpstreamServiceError

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    settings = get_settings()
    if not settings.gemini_api_key:
        raise UpstreamServiceError("GEMINI_API_KEY belum dikonfigurasi di server.")
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
                # Batasi panjang output agar respons JSON lebih cepat & hemat token
                "max_output_tokens": 1024,
            },
        )
    return _model


def _strip_fence(raw_text: str) -> str:
    return _JSON_FENCE_RE.sub("", raw_text).strip()


async def analyze_with_gemini(prompt: str) -> dict[str, Any]:
    """
    Kirim prompt ke Gemini dan kembalikan hasil parsing JSON.
    Retry dengan exponential backoff + cache hasil untuk input identik,
    sesuai mitigasi risiko rate-limit/biaya pada PRD §11.
    """
    cache_key = make_cache_key(prompt)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    result = await _call_gemini(prompt)
    cache_set(cache_key, result)
    return result


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(UpstreamServiceError),
)
async def _call_gemini(prompt: str) -> dict[str, Any]:
    model = _get_model()
    try:
        response = await model.generate_content_async(prompt)
    except Exception as exc:  # noqa: BLE001 - berbagai error dari SDK google
        logger.error("Gemini API error: %s", exc)
        raise UpstreamServiceError("Gagal menghubungi mesin AI (Gemini). Silakan coba lagi.") from exc

    try:
        raw_text = (response.text or "").strip()
    except ValueError as exc:
        logger.error("Gemini menolak/memblokir respons: %s", exc)
        raise UpstreamServiceError(
            "Mesin AI tidak dapat memproses konten ini. Coba dengan teks yang berbeda."
        ) from exc
    if not raw_text:
        raise UpstreamServiceError("Mesin AI mengembalikan respons kosong.")

    cleaned = _strip_fence(raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Gagal parse JSON dari Gemini. Raw: %s", raw_text[:500])
        raise UpstreamServiceError("Mesin AI mengembalikan format respons yang tidak valid.") from exc

    return parsed
