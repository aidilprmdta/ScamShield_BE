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
from app.services.ai_engine.prompt_templates import (
    LINK_ANALYSIS_SYSTEM,
    SYSTEM_INSTRUCTION,
    build_link_prompt,
)
from app.utils.exceptions import UpstreamServiceError

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_model: genai.GenerativeModel | None = None
_link_model: genai.GenerativeModel | None = None

_VALID_RISK_LEVELS = {"low", "medium", "high"}


def _configure_genai() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise UpstreamServiceError("GEMINI_API_KEY belum dikonfigurasi di server.")
    genai.configure(api_key=settings.gemini_api_key)


def _get_model() -> genai.GenerativeModel:
    global _model
    settings = get_settings()
    _configure_genai()
    if _model is None:
        _model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "max_output_tokens": 1024,
            },
        )
    return _model


def _get_link_model() -> genai.GenerativeModel:
    global _link_model
    settings = get_settings()
    _configure_genai()
    if _link_model is None:
        _link_model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=LINK_ANALYSIS_SYSTEM,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "max_output_tokens": 512,
            },
        )
    return _link_model


def _strip_fence(raw_text: str) -> str:
    return _JSON_FENCE_RE.sub("", raw_text).strip()


def _normalize_link_result(parsed: dict[str, Any]) -> dict[str, Any]:
    """Pastikan output Gemini link analysis sesuai kontrak camelCase."""
    raw_score = parsed.get("riskScore", parsed.get("risk_score", 50))
    try:
        score = max(0, min(100, int(raw_score)))
    except (TypeError, ValueError):
        score = 50

    raw_level = str(parsed.get("riskLevel", parsed.get("risk_level", ""))).lower()
    if raw_level not in _VALID_RISK_LEVELS:
        if score >= 67:
            raw_level = "high"
        elif score >= 34:
            raw_level = "medium"
        else:
            raw_level = "low"

    explanation = str(
        parsed.get("explanation") or "Tidak ada penjelasan spesifik dari mesin analisis."
    ).strip()
    recommendation = str(
        parsed.get("recommendation")
        or "Periksa kembali sumber tautan sebelum membukanya."
    ).strip()

    return {
        "riskScore": score,
        "riskLevel": raw_level,
        "explanation": explanation,
        "recommendation": recommendation,
    }


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

    result = await _call_gemini(prompt, model=_get_model())
    cache_set(cache_key, result)
    return result


async def analyze_gemini(
    url: str,
    heuristic_flags: list[str],
    context_text: str | None = None,
) -> dict[str, Any]:
    """
    Layer 3 — Analisis URL + hasil heuristik via Gemini.
    Wajib return JSON:
    {"riskScore": int, "riskLevel": "low|medium|high", "explanation": str, "recommendation": str}
    """
    prompt = build_link_prompt(
        url=url,
        heuristic_flags=heuristic_flags,
        context_text=context_text,
    )
    cache_key = make_cache_key(f"link:{prompt}")
    cached = cache_get(cache_key)
    if cached is not None:
        return _normalize_link_result(cached)

    raw = await _call_gemini(prompt, model=_get_link_model())
    result = _normalize_link_result(raw)
    cache_set(cache_key, result)
    return result


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(UpstreamServiceError),
)
async def _call_gemini(
    prompt: str,
    model: genai.GenerativeModel | None = None,
) -> dict[str, Any]:
    active_model = model or _get_model()
    try:
        response = await active_model.generate_content_async(prompt)
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
