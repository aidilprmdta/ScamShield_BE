"""POST /api/v1/analyze/link — expand → heuristik → URLhaus → Gemini."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeLinkRequest, AnalyzeResponse, ScanType
from app.services.ai_engine.gemini_client import analyze_gemini
from app.services.analysis_persist import persist_analysis_result
from app.services.link_check.custom_rules import check_heuristics, expand_short_link
from app.services.link_check.urlhaus_client import URLHAUS_HIT_RESULT, check_urlhaus
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.validators import normalize_url

router = APIRouter()


@router.post("/analyze/link", response_model=AnalyzeResponse, summary="Cek keamanan tautan/URL")
async def analyze_link(
    payload: AnalyzeLinkRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> AnalyzeResponse:
    url = normalize_url(payload.url)
    resolved_url = await expand_short_link(url)
    flags = check_heuristics(resolved_url)["flags"]
    urlhaus_hit = await check_urlhaus(resolved_url)

    if urlhaus_hit:
        llm_result = URLHAUS_HIT_RESULT
    else:
        llm_result = await analyze_gemini(
            resolved_url,
            flags,
            context_text=payload.context_text,
        )

    result = build_analysis_result(
        scan_type=ScanType.LINK,
        input_summary=url,
        llm_result=llm_result,
        link_reputation={
            "original_url": url,
            "resolved_url": resolved_url,
            "urlhaus_flagged": urlhaus_hit,
            "heuristic_flags": flags,
        },
        force_high_risk=urlhaus_hit,
    )
    result = await persist_analysis_result(
        user_id,
        result,
        high_risk_title="Tautan berisiko tinggi",
    )
    return AnalyzeResponse(data=result)
