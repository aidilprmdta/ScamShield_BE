import asyncio
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeQrRequest, AnalyzeResponse, ScanType
from app.services.ai_engine.gemini_client import analyze_gemini, analyze_with_gemini
from app.services.ai_engine.prompt_templates import build_qr_prompt
from app.services.analysis_persist import persist_analysis_result
from app.services.link_check.custom_rules import check_heuristics, expand_short_link
from app.services.link_check.urlhaus_client import URLHAUS_HIT_RESULT, check_urlhaus
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.validators import looks_like_url, normalize_url

router = APIRouter()


@router.post("/analyze/qr", response_model=AnalyzeResponse, summary="Analisis hasil decode QR code")
async def analyze_qr(
    payload: AnalyzeQrRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> AnalyzeResponse:
    decoded = payload.decoded_content.strip()
    link_reputation = None
    force_high_risk = False

    if looks_like_url(decoded):
        url = normalize_url(decoded)
        resolved_url, urlhaus_hit = await asyncio.gather(
            expand_short_link(url),
            check_urlhaus(url),
        )
        if resolved_url != url and not urlhaus_hit:
            urlhaus_hit = await check_urlhaus(resolved_url)

        flags = check_heuristics(resolved_url)["flags"]
        force_high_risk = urlhaus_hit
        link_reputation = {
            "original_url": url,
            "resolved_url": resolved_url,
            "urlhaus_flagged": urlhaus_hit,
            "heuristic_flags": flags,
        }
        llm_result = (
            URLHAUS_HIT_RESULT
            if urlhaus_hit
            else await analyze_gemini(resolved_url, flags)
        )
    else:
        llm_result = await analyze_with_gemini(
            build_qr_prompt(decoded_content=decoded, is_url=False)
        )

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
