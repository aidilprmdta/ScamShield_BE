"""
Pydantic schemas untuk endpoint /history.
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.models.analyze_schema import AnalysisResult


class HistoryListResponse(BaseModel):
    success: bool = True
    data: list[AnalysisResult]
    next_cursor: Optional[str] = Field(
        default=None, description="Cursor untuk pagination halaman berikutnya"
    )


class HistoryDeleteResponse(BaseModel):
    success: bool = True
    message: str = "Riwayat berhasil dihapus."
