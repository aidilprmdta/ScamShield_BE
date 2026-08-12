"""
Admin-only endpoints untuk mengelola laporan komunitas.
Memerlukan Firebase custom claim 'admin': True.
"""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from firebase_admin import auth as firebase_auth, firestore

from app.core.logging import get_logger
from app.core.security import get_admin_user
from app.models.report_schema import VerifiedStatus
from app.repositories.firestore_repository import (
    _get_db,
    _is_firestore_unavailable,
    _mark_local_fallback,
    _should_use_local,
    count_community_reports,
    get_community_report,
    list_community_reports,
    now_iso,
    update_community_report,
)
from app.services.notify_reporter import notify_reporter_status_updated
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)

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
    if _should_use_local():
        logger.info(
            "Audit log (local): report=%s %s -> %s by %s",
            report_id,
            previous_status,
            new_status,
            admin_uid,
        )
        return

    try:
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
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            logger.info(
                "Audit log skipped (firestore unavailable): report=%s %s -> %s",
                report_id,
                previous_status,
                new_status,
            )
            return
        logger.warning("Gagal menulis audit log: %s", exc)


def _to_list_item(d: dict) -> ReportListItem:
    return ReportListItem(
        report_id=d.get("reportId") or d.get("report_id") or "",
        type=d.get("type", ""),
        content=d.get("content", ""),
        note=d.get("note"),
        verified_status=d.get("verifiedStatus", "pending"),
        reported_by=d.get("reportedBy"),
        created_at=d.get("createdAt", ""),
        verified_by=d.get("verifiedBy"),
        verified_by_email=d.get("verifiedByEmail"),
        verified_at=d.get("verifiedAt"),
    )


@router.get("/reports/count", response_model=ReportCountResponse, summary="Jumlah laporan (admin only)")
async def count_reports(
    status_filter: Optional[str] = "pending",
    _admin_uid: str = Depends(get_admin_user),
) -> ReportCountResponse:
    return ReportCountResponse(count=count_community_reports(status_filter=status_filter))


@router.get("/reports", response_model=ReportListResponse, summary="Daftar semua laporan (admin only)")
async def list_reports(
    status_filter: Optional[str] = None,
    limit: int = 50,
    _admin_uid: str = Depends(get_admin_user),
) -> ReportListResponse:
    docs = list_community_reports(status_filter=status_filter, limit=limit)
    items = [_to_list_item(d) for d in docs]
    return ReportListResponse(data=items, total=len(items))


@router.get("/reports/{report_id}/audit", response_model=AuditLogListResponse, summary="Riwayat audit laporan")
async def get_report_audit(
    report_id: str,
    _admin_uid: str = Depends(get_admin_user),
) -> AuditLogListResponse:
    if _should_use_local():
        return AuditLogListResponse(data=[])

    try:
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
            items.append(
                AuditLogItem(
                    audit_id=d.get("auditId", doc.id),
                    report_id=d.get("reportId", report_id),
                    action=d.get("action", ""),
                    previous_status=d.get("previousStatus"),
                    new_status=d.get("newStatus", ""),
                    admin_uid=d.get("adminUid", ""),
                    admin_email=d.get("adminEmail"),
                    created_at=d.get("createdAt", ""),
                )
            )
        return AuditLogListResponse(data=items)
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return AuditLogListResponse(data=[])
        logger.warning("Gagal memuat audit log: %s", exc)
        return AuditLogListResponse(data=[])


@router.patch("/reports/{report_id}", response_model=UpdateReportStatusResponse, summary="Update status laporan (admin only)")
async def update_report_status(
    report_id: str,
    payload: UpdateReportStatusRequest,
    admin_uid: str = Depends(get_admin_user),
) -> UpdateReportStatusResponse:
    report_data = get_community_report(report_id)
    if not report_data:
        raise NotFoundError(f"Laporan {report_id} tidak ditemukan.")

    reported_by = report_data.get("reportedBy")
    report_type = report_data.get("type", "")
    content = report_data.get("content", "")
    previous_status = report_data.get("verifiedStatus")

    verified_at = now_iso()
    admin_email = _admin_email(admin_uid)

    updated = update_community_report(
        report_id,
        {
            "verifiedStatus": payload.status.value,
            "verifiedBy": admin_uid,
            "verifiedByEmail": admin_email,
            "verifiedAt": verified_at,
        },
    )
    if not updated:
        raise NotFoundError(f"Laporan {report_id} tidak ditemukan.")

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
