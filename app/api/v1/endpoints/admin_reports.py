"""
Admin-only endpoints untuk mengelola laporan komunitas.
Memerlukan Firebase custom claim 'admin': True.
"""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from firebase_admin import auth as firebase_auth, firestore

from app.core.security import get_admin_user
from app.models.report_schema import VerifiedStatus
from app.repositories.firestore_repository import _get_db, now_iso
from app.services.notify_reporter import notify_reporter_status_updated
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/admin", tags=["Admin"])

AUDIT_COLLECTION = "report_audit_logs"


class ReportListItem(BaseModel):
    report_id: str
    type: str
    content: str
    note: Optional[str] = None
    verified_status: str
    reported_by: Optional[str] = None
    created_at: str
    verified_by: Optional[str] = None
    verified_by_email: Optional[str] = None
    verified_at: Optional[str] = None


class ReportListResponse(BaseModel):
    success: bool = True
    data: list[ReportListItem]
    total: int


class UpdateReportStatusRequest(BaseModel):
    status: VerifiedStatus


class UpdateReportStatusResponse(BaseModel):
    success: bool = True
    message: str
    verified_by: Optional[str] = None
    verified_by_email: Optional[str] = None
    verified_at: Optional[str] = None


class ReportCountResponse(BaseModel):
    success: bool = True
    count: int


class AuditLogItem(BaseModel):
    audit_id: str
    report_id: str
    action: str
    previous_status: Optional[str] = None
    new_status: str
    admin_uid: str
    admin_email: Optional[str] = None
    created_at: str


class AuditLogListResponse(BaseModel):
    success: bool = True
    data: list[AuditLogItem]


def _admin_email(admin_uid: str) -> Optional[str]:
    try:
        return firebase_auth.get_user(admin_uid).email
    except Exception:
        return None


def _write_audit_log(
    report_id: str,
    action: str,
    previous_status: Optional[str],
    new_status: str,
    admin_uid: str,
    admin_email: Optional[str],
    created_at: str,
) -> None:
    db = _get_db()
    audit_id = str(uuid4())
    db.collection(AUDIT_COLLECTION).document(audit_id).set(
        {
            "auditId": audit_id,
            "reportId": report_id,
            "action": action,
            "previousStatus": previous_status,
            "newStatus": new_status,
            "adminUid": admin_uid,
            "adminEmail": admin_email,
            "createdAt": created_at,
        }
    )


@router.get("/reports/count", response_model=ReportCountResponse, summary="Jumlah laporan (admin only)")
async def count_reports(
    status_filter: Optional[str] = "pending",
    _admin_uid: str = Depends(get_admin_user),
) -> ReportCountResponse:
    db = _get_db()
    query = db.collection("community_reports")
    if status_filter:
        query = query.where("verifiedStatus", "==", status_filter)
    count = sum(1 for _ in query.stream())
    return ReportCountResponse(count=count)


@router.get("/reports", response_model=ReportListResponse, summary="Daftar semua laporan (admin only)")
async def list_reports(
    status_filter: Optional[str] = None,
    limit: int = 50,
    _admin_uid: str = Depends(get_admin_user),
) -> ReportListResponse:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    
    db = _get_db()
    query = db.collection("community_reports").order_by("createdAt", direction=firestore.Query.DESCENDING)

    if status_filter:
        query = query.where("verifiedStatus", "==", status_filter)

    docs = query.limit(limit).stream()

    items = []
    doc_count = 0
    for doc in docs:
        doc_count += 1
        d = doc.to_dict() or {}
        items.append(ReportListItem(
            report_id=d.get("reportId", doc.id),
            type=d.get("type", ""),
            content=d.get("content", ""),
            note=d.get("note"),
            verified_status=d.get("verifiedStatus", "pending"),
            reported_by=d.get("reportedBy"),
            created_at=d.get("createdAt", ""),
            verified_by=d.get("verifiedBy"),
            verified_by_email=d.get("verifiedByEmail"),
            verified_at=d.get("verifiedAt"),
        ))
    
    logger.info(f"Admin reports query: found {doc_count} documents, status_filter={status_filter}")
    if doc_count > 0:
        logger.info(f"First report: {items[0].dict() if items else 'none'}")

    return ReportListResponse(data=items, total=len(items))


@router.get("/reports/{report_id}/audit", response_model=AuditLogListResponse, summary="Riwayat audit laporan")
async def get_report_audit(
    report_id: str,
    _admin_uid: str = Depends(get_admin_user),
) -> AuditLogListResponse:
    db = _get_db()
    docs = (
        db.collection(AUDIT_COLLECTION)
        .where("reportId", "==", report_id)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(50)
        .stream()
    )
    items = []
    for doc in docs:
        d = doc.to_dict() or {}
        items.append(AuditLogItem(
            audit_id=d.get("auditId", doc.id),
            report_id=d.get("reportId", report_id),
            action=d.get("action", ""),
            previous_status=d.get("previousStatus"),
            new_status=d.get("newStatus", ""),
            admin_uid=d.get("adminUid", ""),
            admin_email=d.get("adminEmail"),
            created_at=d.get("createdAt", ""),
        ))
    return AuditLogListResponse(data=items)


@router.patch("/reports/{report_id}", response_model=UpdateReportStatusResponse, summary="Update status laporan (admin only)")
async def update_report_status(
    report_id: str,
    payload: UpdateReportStatusRequest,
    admin_uid: str = Depends(get_admin_user),
) -> UpdateReportStatusResponse:
    db = _get_db()
    doc_ref = db.collection("community_reports").document(report_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise NotFoundError(f"Laporan {report_id} tidak ditemukan.")

    report_data = doc.to_dict() or {}
    reported_by = report_data.get("reportedBy")
    report_type = report_data.get("type", "")
    content = report_data.get("content", "")
    previous_status = report_data.get("verifiedStatus")

    verified_at = now_iso()
    admin_email = _admin_email(admin_uid)

    doc_ref.update(
        {
            "verifiedStatus": payload.status.value,
            "verifiedBy": admin_uid,
            "verifiedByEmail": admin_email,
            "verifiedAt": verified_at,
        }
    )

    _write_audit_log(
        report_id=report_id,
        action=payload.status.value,
        previous_status=previous_status,
        new_status=payload.status.value,
        admin_uid=admin_uid,
        admin_email=admin_email,
        created_at=verified_at,
    )

    if reported_by:
        notify_reporter_status_updated(
            reporter_uid=reported_by,
            report_id=report_id,
            status=payload.status.value,
            report_type=report_type,
            content=content,
        )

    return UpdateReportStatusResponse(
        message=f"Status laporan diubah ke '{payload.status.value}'",
        verified_by=admin_uid,
        verified_by_email=admin_email,
        verified_at=verified_at,
    )
