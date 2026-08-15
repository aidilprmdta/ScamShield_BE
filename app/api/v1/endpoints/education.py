"""
GET /api/v1/education        -> daftar artikel/kuis literasi digital, bisa difilter per kategori
GET /api/v1/education/{id}   -> detail satu artikel/simulasi
Sesuai PRD §5 poin 9 & §6 (Konten Edukasi - Should Have).
"""
from typing import Optional

from fastapi import APIRouter, Query

from app.core.logging import get_logger
from app.models.education_schema import (
    EducationContentDetail,
    EducationContentSummary,
    EducationDetailResponse,
    EducationListResponse,
)
from app.repositories.firestore_repository import get_education_content, list_education_content
from app.utils.exceptions import NotFoundError

router = APIRouter()
logger = get_logger(__name__)


@router.get("/education", response_model=EducationListResponse, summary="Daftar konten edukasi")
async def get_education_list(
    category: Optional[str] = Query(
        default=None, description="Filter kategori, mis. 'Phishing', 'QRIS Palsu'"
    ),
) -> EducationListResponse:
    items = list_education_content(category=category)
    summaries: list[EducationContentSummary] = []
    for item in items:
        try:
            summaries.append(EducationContentSummary.model_validate(item))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skip konten edukasi rusak id=%s: %s", item.get("id"), exc)
    return EducationListResponse(data=summaries)


@router.get(
    "/education/{content_id}",
    response_model=EducationDetailResponse,
    summary="Detail satu artikel/simulasi edukasi",
)
async def get_education_detail(content_id: str) -> EducationDetailResponse:
    content = get_education_content(content_id)
    if content is None:
        raise NotFoundError("Konten edukasi tidak ditemukan.")
    try:
        return EducationDetailResponse(data=EducationContentDetail.model_validate(content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Konten edukasi %s tidak valid: %s", content_id, exc)
        raise NotFoundError("Konten edukasi tidak ditemukan.") from exc
