"""
POST /api/v1/analyze/qr
Analisis hasil decode QR code (dari com.google.mlkit:barcode-scanning + CameraX di client).
Jika hasil decode berupa URL -> dijalankan pipeline sama seperti analyze/link (Safe Browsing
+ custom rules). Jika berupa teks biasa -> dianalisis langsung sebagai konten.
Sesuai PRD §13.
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeQrRequest, AnalyzeResponse, ScanType
from app.services.ai_engine.gemini_client import analyze_with_gemini
from app.services.ai_engine.prompt_templates import build_link_prompt, build_qr_prompt
from app.services.analysis_persist import persist_analysis_result
from app.services.link_check.custom_rules import run_link_heuristics
from app.services.link_check.safe_browsing_client import check_url_reputation
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.validators import looks_like_url, normalize_url

router = APIRouter()


@router.post("/analyze/qr", response_model=AnalyzeResponse, summary="Analisis hasil decode QR code")
async def analyze_qr(
    payload: AnalyzeQrRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> AnalyzeResponse:
    decoded = payload.decoded_content.strip()
    is_url = looks_like_url(decoded)

    link_reputation = None
    force_high_risk = False

    if is_url:
        url = normalize_url(decoded)
        heuristics = await run_link_heuristics(url)
        resolved_url = heuristics["resolved_url"]
        reputation = await check_url_reputation(resolved_url)
        force_high_risk = reputation["is_flagged"]

        link_reputation = {
            "original_url": url,
            "resolved_url": resolved_url,
            "safe_browsing_flagged": reputation["is_flagged"],
            "safe_browsing_threat_types": reputation["threat_types"],
            "heuristic_flags": heuristics["flags"],
        }
        prompt = build_link_prompt(
            url=resolved_url,
            context_text="Tautan ini berasal dari hasil pindai QR code.",
            safe_browsing_verdict=reputation["verdict"],
            custom_rule_flags=heuristics["flags"],
        )
    else:
        prompt = build_qr_prompt(decoded_content=decoded, is_url=False)

    llm_result = await analyze_with_gemini(prompt)

    result = build_analysis_result(
        scan_type=ScanType.QR,
        input_summary=decoded,
        llm_result=llm_result,
        link_reputation=link_reputation,
        force_high_risk=force_high_risk,
    )
    result = await persist_analysis_result(
        user_id,
        result,
        high_risk_title="QR berisiko tinggi",
    )

    return AnalyzeResponse(data=result)
