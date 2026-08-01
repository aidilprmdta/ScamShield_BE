"""
GET /api/v1/education        -> daftar artikel/kuis literasi digital, bisa difilter per kategori
GET /api/v1/education/{id}   -> detail satu artikel/simulasi
Sesuai PRD §5 poin 9 & §6 (Konten Edukasi - Should Have).
"""
from typing import Optional

from fastapi import APIRouter, Query

from app.models.education_schema import EducationDetailResponse, EducationListResponse
from app.repositories.firestore_repository import get_education_content, list_education_content
from app.utils.exceptions import NotFoundError

router = APIRouter()


@router.get("/education", response_model=EducationListResponse, summary="Daftar konten edukasi")
async def get_education_list(
    category: Optional[str] = Query(
        default=None, description="Filter kategori, mis. 'Phishing', 'QRIS Palsu'"
    ),
) -> EducationListResponse:
    items = list_education_content(category=category)
    return EducationListResponse(data=items)


@router.get(
    "/education/{content_id}",
    response_model=EducationDetailResponse,
    summary="Detail satu artikel/simulasi edukasi",
)
async def get_education_detail(content_id: str) -> EducationDetailResponse:
    content = get_education_content(content_id)
    if content is None:
        raise NotFoundError("Konten edukasi tidak ditemukan.")
    return EducationDetailResponse(data=content)
