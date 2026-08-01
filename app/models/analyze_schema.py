"""
Pydantic schemas untuk request/response endpoint /analyze/*.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScanType(str, Enum):
    CHAT = "chat"
    SCREENSHOT = "screenshot"
    LINK = "link"
    QR = "qr"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedAction(str, Enum):
    IGNORE = "ignore"          # abaikan, tampak aman
    PROCEED_CAREFULLY = "proceed_carefully"  # lanjutkan dengan hati-hati
    BLOCK = "block"             # blokir pengirim/nomor
    REPORT = "report"           # laporkan sebagai penipuan


# ---------- Requests ----------

class AnalyzeChatRequest(BaseModel):
    text: str = Field(..., description="Isi chat/SMS, atau hasil OCR dari screenshot")
    source: Optional[str] = Field(
        default=None, description="Sumber pesan, mis. 'sms', 'whatsapp', 'screenshot_ocr'"
    )
    ocr_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Confidence OCR bila teks berasal dari screenshot (0-1)",
    )


class AnalyzeLinkRequest(BaseModel):
    url: str = Field(..., description="Tautan/URL yang ingin diverifikasi")
    context_text: Optional[str] = Field(
        default=None, description="Teks pesan pengantar tautan (opsional, menambah konteks LLM)"
    )


class AnalyzeQrRequest(BaseModel):
    decoded_content: str = Field(..., description="Hasil decode QR code (URL, teks, atau data lain)")


# ---------- Response ----------

class RedFlag(BaseModel):
    label: str
    detail: str


class AnalysisResult(BaseModel):
    scan_id: Optional[str] = None
    type: ScanType
    input_summary: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    explanation: str
    red_flags: list[RedFlag] = Field(default_factory=list)
    recommendation: RecommendedAction
    recommendation_text: str
    related_education_category: Optional[str] = Field(
        default=None,
        description="Kategori modus terdeteksi, dipakai FE untuk tombol 'Pelajari lebih lanjut'",
    )
    link_reputation: Optional[dict] = Field(
        default=None, description="Detail hasil Safe Browsing + custom rules (khusus type=link/qr)"
    )
    created_at: str


class AnalyzeResponse(BaseModel):
    success: bool = True
    data: AnalysisResult
