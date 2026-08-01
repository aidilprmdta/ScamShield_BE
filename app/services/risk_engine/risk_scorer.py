"""
Gabungkan hasil LLM (Gemini) dan/atau hasil link check (Safe Browsing + custom rules)
menjadi objek AnalysisResult final yang konsisten dengan schema.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.analyze_schema import (
    AnalysisResult,
    RecommendedAction,
    RedFlag,
    RiskLevel,
    ScanType,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_VALID_RISK_LEVELS = {r.value for r in RiskLevel}
_VALID_RECOMMENDATIONS = {r.value for r in RecommendedAction}


def _clamp_score(score: Any) -> int:
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 50
    return max(0, min(100, score))


def _level_from_score(score: int) -> RiskLevel:
    if score >= 67:
        return RiskLevel.HIGH
    if score >= 34:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _safe_risk_level(raw: Any, score: int) -> RiskLevel:
    if isinstance(raw, str) and raw.lower() in _VALID_RISK_LEVELS:
        return RiskLevel(raw.lower())
    return _level_from_score(score)


def _safe_recommendation(raw: Any, level: RiskLevel) -> RecommendedAction:
    if isinstance(raw, str) and raw.lower() in _VALID_RECOMMENDATIONS:
        return RecommendedAction(raw.lower())
    defaults = {
        RiskLevel.LOW: RecommendedAction.IGNORE,
        RiskLevel.MEDIUM: RecommendedAction.PROCEED_CAREFULLY,
        RiskLevel.HIGH: RecommendedAction.BLOCK,
    }
    return defaults[level]


def build_analysis_result(
    scan_type: ScanType,
    input_summary: str,
    llm_result: dict[str, Any],
    link_reputation: Optional[dict[str, Any]] = None,
    force_high_risk: bool = False,
) -> AnalysisResult:
    """
    Args:
        scan_type: tipe scan (chat/screenshot/link/qr)
        input_summary: cuplikan input yang dianalisis (untuk ditampilkan/disimpan)
        llm_result: dict hasil parsing JSON dari Gemini
        link_reputation: hasil gabungan Safe Browsing + custom rules (khusus link/qr)
        force_high_risk: paksa risk_level=high (mis. saat Safe Browsing menandai berbahaya)
    """
    score = _clamp_score(llm_result.get("risk_score"))
    if force_high_risk:
        score = max(score, 85)

    level = _safe_risk_level(llm_result.get("risk_level"), score)
    if force_high_risk:
        level = RiskLevel.HIGH

    # Saat force_high_risk (mis. Safe Browsing menandai berbahaya), rekomendasi LLM
    # yang lama (dihasilkan sebelum override) tidak lagi relevan -> pakai default level.
    if force_high_risk:
        recommendation = _safe_recommendation(None, level)
    else:
        recommendation = _safe_recommendation(llm_result.get("recommendation"), level)

    explanation = str(
        llm_result.get("explanation")
        or "Tidak ada penjelasan spesifik dari mesin analisis."
    ).strip()

    recommendation_text = str(
        llm_result.get("recommendation_text")
        or _default_recommendation_text(recommendation)
    ).strip()

    raw_flags = llm_result.get("red_flags") or []
    red_flags: list[RedFlag] = []
    for item in raw_flags:
        if isinstance(item, dict) and item.get("label"):
            red_flags.append(
                RedFlag(label=str(item["label"]), detail=str(item.get("detail", "")))
            )

    category = llm_result.get("category")
    category = str(category).strip() if category and str(category).lower() != "null" else None

    return AnalysisResult(
        type=scan_type,
        input_summary=input_summary[:300],
        risk_score=score,
        risk_level=level,
        explanation=explanation,
        red_flags=red_flags,
        recommendation=recommendation,
        recommendation_text=recommendation_text,
        related_education_category=category if level != RiskLevel.LOW else category,
        link_reputation=link_reputation,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _default_recommendation_text(action: RecommendedAction) -> str:
    return {
        RecommendedAction.IGNORE: "Tampak aman, tidak perlu tindakan khusus.",
        RecommendedAction.PROCEED_CAREFULLY: "Lanjutkan dengan hati-hati, jangan bagikan data pribadi/OTP.",
        RecommendedAction.BLOCK: "Sebaiknya blokir pengirim/nomor ini.",
        RecommendedAction.REPORT: "Sebaiknya laporkan sebagai penipuan ke pihak berwenang/komunitas.",
    }[action]
