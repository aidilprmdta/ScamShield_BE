"""
Pydantic schemas untuk endpoint /report (pelaporan komunitas).
"""
from enum import Enum

from pydantic import BaseModel, Field


class ReportType(str, Enum):
    CHAT = "chat"
    LINK = "link"
    QR = "qr"
    OTHER = "other"


class VerifiedStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CommunityReportRequest(BaseModel):
    type: ReportType
    content: str = Field(..., description="Isi laporan: teks chat, URL, atau deskripsi modus")
    note: str | None = Field(default=None, description="Catatan tambahan dari pelapor")


class CommunityReportResult(BaseModel):
    report_id: str
    type: ReportType
    content: str
    note: str | None
    verified_status: VerifiedStatus
    reported_by: str | None
    created_at: str


class CommunityReportResponse(BaseModel):
    success: bool = True
    data: CommunityReportResult
