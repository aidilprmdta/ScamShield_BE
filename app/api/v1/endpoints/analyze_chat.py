"""
POST /api/v1/analyze/chat
Analisis teks chat/SMS (diketik langsung, atau hasil OCR dari screenshot).
Sesuai PRD §13: pola yang sama dipakai untuk analyze/screenshot (teks hasil OCR
dikirim ke endpoint ini dengan source="screenshot_ocr").
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_optional_user
from app.models.analyze_schema import AnalyzeChatRequest, AnalyzeResponse, ScanType
from app.services.ai_engine.gemini_client import analyze_with_gemini
from app.services.ai_engine.prompt_templates import build_chat_prompt
from app.services.analysis_persist import persist_analysis_result
from app.services.risk_engine.risk_scorer import build_analysis_result
from app.utils.exceptions import OcrLowConfidenceError
from app.utils.validators import MIN_OCR_CONFIDENCE, validate_chat_text

router = APIRouter()


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
    result = await persist_analysis_result(
        user_id,
        result,
        high_risk_title="Ancaman tinggi terdeteksi",
    )

    return AnalyzeResponse(data=result)
