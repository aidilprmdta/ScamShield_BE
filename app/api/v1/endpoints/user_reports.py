"""
Endpoint laporan milik user yang login.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.repositories.firestore_repository import (
    count_user_reports,
    get_community_report,
    list_user_reports,
)
from app.utils.exceptions import NotFoundError, UnauthorizedError

router = APIRouter(prefix="/reports", tags=["Reports"])


class UserReportItem(BaseModel):
    report_id: str
    type: str
    content: str
    note: Optional[str] = None
    verified_status: str
    created_at: str
    verified_at: Optional[str] = None


class UserReportListResponse(BaseModel):
    success: bool = True
    data: list[UserReportItem]


class UserReportDetailResponse(BaseModel):
    success: bool = True
    data: UserReportItem


class ReportCountResponse(BaseModel):
    success: bool = True
    count: int


def _to_item(data: dict) -> UserReportItem:
    return UserReportItem(
        report_id=data.get("reportId") or data.get("report_id") or "",
        type=data.get("type", ""),
        content=data.get("content", ""),
        note=data.get("note"),
        verified_status=data.get("verifiedStatus", "pending"),
        created_at=data.get("createdAt", ""),
        verified_at=data.get("verifiedAt"),
    )


@router.get("/mine", response_model=UserReportListResponse, summary="Daftar laporan user yang login")
async def list_my_reports(
    uid: str = Depends(get_current_user),
    limit: int = 50,
) -> UserReportListResponse:
    docs = list_user_reports(uid, limit=limit)
    return UserReportListResponse(data=[_to_item(d) for d in docs])


@router.get("/mine/count", response_model=ReportCountResponse, summary="Jumlah laporan user")
async def count_my_reports(
    uid: str = Depends(get_current_user),
    status_filter: Optional[str] = "pending",
) -> ReportCountResponse:
    return ReportCountResponse(count=count_user_reports(uid, status_filter=status_filter))


@router.get("/{report_id}", response_model=UserReportDetailResponse, summary="Detail laporan milik user")
async def get_my_report(
    report_id: str,
    uid: str = Depends(get_current_user),
) -> UserReportDetailResponse:
    data = get_community_report(report_id)
    if not data:
        raise NotFoundError(f"Laporan {report_id} tidak ditemukan.")

    if data.get("reportedBy") != uid:
        raise UnauthorizedError("Anda tidak memiliki akses ke laporan ini.")

    return UserReportDetailResponse(data=_to_item(data))
