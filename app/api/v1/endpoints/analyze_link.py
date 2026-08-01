"""
POST /api/v1/analyze/link
Cek keamanan URL: Safe Browsing API + custom heuristik (shortlink/domain) + LLM.
Mengikuti alur end-to-end pada PRD §13.
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.logging import get_logger
from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeLinkRequest, AnalyzeResponse, ScanType
from app.repositories.firestore_repository import save_scan_history
from app.services.ai_engine.gemini_client import analyze_with_gemini
from app.services.ai_engine.prompt_templates import build_link_prompt
from app.services.link_check.custom_rules import run_link_heuristics
from app.services.link_check.safe_browsing_client import check_url_reputation
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.validators import normalize_url

router = APIRouter()
logger = get_logger(__name__)


@router.post("/analyze/link", response_model=AnalyzeResponse, summary="Cek keamanan tautan/URL")
async def analyze_link(
    payload: AnalyzeLinkRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> AnalyzeResponse:
    url = normalize_url(payload.url)

    # 1. Custom logic: expand shortlink + heuristik domain
    heuristics = await run_link_heuristics(url)
    resolved_url = heuristics["resolved_url"]

    # 2. Google Safe Browsing
    reputation = await check_url_reputation(resolved_url)

    # 3. Kirim konteks gabungan ke LLM untuk analisis & penjelasan
    prompt = build_link_prompt(
        url=resolved_url,
        context_text=payload.context_text,
        safe_browsing_verdict=reputation["verdict"],
        custom_rule_flags=heuristics["flags"],
    )
    llm_result = await analyze_with_gemini(prompt)

    link_reputation = {
        "original_url": url,
        "resolved_url": resolved_url,
        "safe_browsing_flagged": reputation["is_flagged"],
        "safe_browsing_threat_types": reputation["threat_types"],
        "heuristic_flags": heuristics["flags"],
    }

    result = build_analysis_result(
        scan_type=ScanType.LINK,
        input_summary=url,
        llm_result=llm_result,
        link_reputation=link_reputation,
        force_high_risk=reputation["is_flagged"],
    )

    try:
        scan_id = save_scan_history(user_id, result.model_dump(mode="json"))
        result.scan_id = scan_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal menyimpan scan_history: %s", exc)

    return AnalyzeResponse(data=result)
