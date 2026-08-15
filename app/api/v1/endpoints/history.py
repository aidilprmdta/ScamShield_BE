"""
GET    /api/v1/history        -> ambil riwayat analisis milik user login
DELETE /api/v1/history/{id}   -> hapus 1 riwayat milik user login
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.analyze_schema import AnalysisResult
from app.models.history_schema import HistoryDeleteResponse, HistoryListResponse
from app.repositories.firestore_repository import delete_scan_history, list_scan_history
from app.utils.exceptions import NotFoundError

router = APIRouter()
logger = get_logger(__name__)


def _parse_history_item(doc: dict) -> Optional[AnalysisResult]:
    try:
        return AnalysisResult.model_validate(doc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skip riwayat rusak scan_id=%s: %s", doc.get("scan_id") or doc.get("scanId"), exc)
        return None


@router.get("/history", response_model=HistoryListResponse, summary="Ambil riwayat analisis pengguna")
async def get_history(
    user_id: str = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None, description="scanId item terakhir dari halaman sebelumnya"),
) -> HistoryListResponse:
    raw_items = list_scan_history(user_id=user_id, limit=limit, start_after_id=cursor)
    items = [parsed for parsed in (_parse_history_item(d) for d in raw_items) if parsed is not None]
    next_cursor = None
    if len(raw_items) == limit and raw_items:
        last = raw_items[-1]
        next_cursor = last.get("scanId") or last.get("scan_id")
    return HistoryListResponse(data=items, next_cursor=next_cursor)


@router.delete(
    "/history/{scan_id}", response_model=HistoryDeleteResponse, summary="Hapus satu riwayat analisis"
)
async def delete_history_item(
    scan_id: str,
    user_id: str = Depends(get_current_user),
) -> HistoryDeleteResponse:
    deleted = delete_scan_history(user_id=user_id, scan_id=scan_id)
    if not deleted:
        raise NotFoundError("Riwayat tidak ditemukan atau bukan milik Anda.")
    return HistoryDeleteResponse()
