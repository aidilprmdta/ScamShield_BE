"""
Endpoint laporan milik user yang login.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from firebase_admin import firestore

from app.core.security import get_current_user
from app.repositories.firestore_repository import _get_db
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


def _to_item(doc_id: str, data: dict) -> UserReportItem:
    return UserReportItem(
        report_id=data.get("reportId", doc_id),
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
    db = _get_db()
    docs = (
        db.collection("community_reports")
        .where("reportedBy", "==", uid)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    items = [_to_item(doc.id, doc.to_dict() or {}) for doc in docs]
    return UserReportListResponse(data=items)


@router.get("/mine/count", response_model=ReportCountResponse, summary="Jumlah laporan user")
async def count_my_reports(
    uid: str = Depends(get_current_user),
    status_filter: Optional[str] = "pending",
) -> ReportCountResponse:
    db = _get_db()
    query = db.collection("community_reports").where("reportedBy", "==", uid)
    if status_filter:
        query = query.where("verifiedStatus", "==", status_filter)
    count = sum(1 for _ in query.stream())
    return ReportCountResponse(count=count)


@router.get("/{report_id}", response_model=UserReportDetailResponse, summary="Detail laporan milik user")
async def get_my_report(
    report_id: str,
    uid: str = Depends(get_current_user),
) -> UserReportDetailResponse:
    db = _get_db()
    doc = db.collection("community_reports").document(report_id).get()
    if not doc.exists:
        raise NotFoundError(f"Laporan {report_id} tidak ditemukan.")

    data = doc.to_dict() or {}
    if data.get("reportedBy") != uid:
        raise UnauthorizedError("Anda tidak memiliki akses ke laporan ini.")

    return UserReportDetailResponse(data=_to_item(doc.id, data))
