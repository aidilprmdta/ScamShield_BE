"""
POST /api/v1/report
Pelaporan komunitas atas modus penipuan baru (PRD §6: "Pelaporan Komunitas" - Should Have).
Login opsional: pengguna anonim tetap bisa melapor, namun reportedBy akan null.
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.core.security import get_optional_user
from app.models.report_schema import (
    CommunityReportRequest,
    CommunityReportResponse,
    CommunityReportResult,
    VerifiedStatus,
)
from app.repositories.firestore_repository import now_iso, save_community_report
from app.services.notify_admin import notify_admins_new_report

router = APIRouter()


@router.post("/report", response_model=CommunityReportResponse, summary="Laporkan modus penipuan baru")
async def submit_report(
    payload: CommunityReportRequest,
    user_id: Optional[str] = Depends(get_optional_user),
) -> CommunityReportResponse:
    created_at = now_iso()
    doc = {
        "type": payload.type.value,
        "content": payload.content.strip(),
        "note": payload.note,
        "verifiedStatus": VerifiedStatus.PENDING.value,
        "createdAt": created_at,
    }
    report_id = save_community_report(user_id, doc)

    result = CommunityReportResult(
        report_id=report_id,
        type=payload.type,
        content=doc["content"],
        note=payload.note,
        verified_status=VerifiedStatus.PENDING,
        reported_by=user_id,
        created_at=created_at,
    )
    notify_admins_new_report(report_id, payload.type.value, doc["content"])

    return CommunityReportResponse(data=result)
