"""
POST /api/v1/analyze/chat
Analisis teks chat/SMS (diketik langsung, atau hasil OCR dari screenshot).
Sesuai PRD §13: pola yang sama dipakai untuk analyze/screenshot (teks hasil OCR
dikirim ke endpoint ini dengan source="screenshot_ocr").
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.logging import get_logger
from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeChatRequest, AnalyzeResponse, ScanType
from app.repositories.firestore_repository import save_scan_history
from app.services.ai_engine.gemini_client import analyze_with_gemini
from app.services.ai_engine.prompt_templates import build_chat_prompt
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.exceptions import OcrLowConfidenceError
from app.utils.validators import MIN_OCR_CONFIDENCE, validate_chat_text

router = APIRouter()
logger = get_logger(__name__)


@router.post("/analyze/chat", response_model=AnalyzeResponse, summary="Analisis teks chat/SMS")
async def analyze_chat(
    payload: AnalyzeChatRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> AnalyzeResponse:
    text = validate_chat_text(payload.text)

    # Fallback OCR gagal/kualitas rendah (PRD §11: minta input manual jika confidence rendah)
    if payload.ocr_confidence is not None and payload.ocr_confidence < MIN_OCR_CONFIDENCE:
        raise OcrLowConfidenceError()

    scan_type = (
        ScanType.SCREENSHOT if payload.source == "screenshot_ocr" else ScanType.CHAT
    )

    prompt = build_chat_prompt(text=text, source=payload.source)
    llm_result = await analyze_with_gemini(prompt)

    result = build_analysis_result(
        scan_type=scan_type,
        input_summary=text,
        llm_result=llm_result,
    )

    try:
        scan_id = save_scan_history(user_id, result.model_dump(mode="json"))
        result.scan_id = scan_id
    except Exception as exc:  # noqa: BLE001
        # Jangan gagalkan response analisis hanya karena penyimpanan riwayat gagal
        logger.warning("Gagal menyimpan scan_history: %s", exc)

    return AnalyzeResponse(data=result)
