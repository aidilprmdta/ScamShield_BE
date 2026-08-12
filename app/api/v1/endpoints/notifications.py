from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.notification_schema import (
    MarkNotificationReadResponse,
    NotificationItem,
    NotificationListResponse,
    RegisterFcmTokenRequest,
)
from app.repositories.firestore_repository import (
    list_user_notifications,
    mark_user_notification_read,
    save_fcm_token,
)
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/register-token")
async def register_fcm_token(
    request: RegisterFcmTokenRequest,
    uid: str = Depends(get_current_user),
):
    save_fcm_token(uid, request.fcm_token)
    return {"success": True, "message": "Token registered"}


@router.get("", response_model=NotificationListResponse, summary="Daftar notifikasi pengguna")
async def get_notifications(
    uid: str = Depends(get_current_user),
) -> NotificationListResponse:
    items = list_user_notifications(uid)
    return NotificationListResponse(
        data=[
            NotificationItem(
                id=d["id"],
                title=d.get("title", ""),
                body=d.get("body", ""),
                type=d.get("type", ""),
                read=bool(d.get("read", False)),
                created_at=d.get("created_at", ""),
                data=d.get("data") or {},
            )
            for d in items
        ]
    )


@router.patch(
    "/{notif_id}/read",
    response_model=MarkNotificationReadResponse,
    summary="Tandai notifikasi sudah dibaca",
)
async def mark_read(
    notif_id: str,
    uid: str = Depends(get_current_user),
) -> MarkNotificationReadResponse:
    ok = mark_user_notification_read(uid, notif_id)
    if not ok:
        raise NotFoundError("Notifikasi tidak ditemukan.")
    return MarkNotificationReadResponse()
