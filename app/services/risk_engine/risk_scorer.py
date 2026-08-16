"""
Gabungkan hasil LLM (Gemini) dan/atau hasil link check (URLhaus + heuristik)
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


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


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
        llm_result: dict hasil parsing JSON dari Gemini (snake_case atau camelCase)
        link_reputation: hasil gabungan URLhaus + heuristik (khusus link/qr)
        force_high_risk: paksa risk_level=high (mis. saat URLhaus menandai berbahaya)
    """
    score = _clamp_score(_pick(llm_result, "risk_score", "riskScore", default=50))
    if force_high_risk:
        score = max(score, 95)

    level = _safe_risk_level(
        _pick(llm_result, "risk_level", "riskLevel"),
        score,
    )
    if force_high_risk:
        level = RiskLevel.HIGH

    if force_high_risk:
        recommendation = _safe_recommendation(None, level)
    else:
        recommendation = _safe_recommendation(
            _pick(llm_result, "recommendation"),
            level,
        )

    explanation = str(
        _pick(llm_result, "explanation")
        or "Tidak ada penjelasan spesifik dari mesin analisis."
    ).strip()

    # analyze_gemini mengembalikan recommendation sebagai saran teks (ID);
    # chat/screenshot memakai recommendation_text terpisah + enum recommendation.
    raw_rec = _pick(llm_result, "recommendation")
    raw_rec_text = _pick(llm_result, "recommendation_text")
    if isinstance(raw_rec, str) and raw_rec.lower() not in _VALID_RECOMMENDATIONS:
        recommendation_text = raw_rec.strip() or _default_recommendation_text(recommendation)
        recommendation = _safe_recommendation(None, level)
    else:
        recommendation_text = str(
            raw_rec_text or _default_recommendation_text(recommendation)
        ).strip()

    raw_flags = _pick(llm_result, "red_flags", "redFlags") or []
    red_flags: list[RedFlag] = []
    for item in raw_flags:
        if isinstance(item, dict) and item.get("label"):
            red_flags.append(
                RedFlag(label=str(item["label"]), detail=str(item.get("detail", "")))
            )

    category = _pick(llm_result, "category")
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
        related_education_category=category if level != RiskLevel.LOW else None,
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
