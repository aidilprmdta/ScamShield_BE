"""
Send FCM notification to report owner when status changes.
"""
from firebase_admin import messaging

from app.core.logging import get_logger
from app.repositories import local_store
from app.repositories.firestore_repository import (
    add_user_notification,
    _get_db,
    _is_firestore_unavailable,
    _mark_local_fallback,
    _should_use_local,
)

logger = get_logger(__name__)


def _get_reporter_token(reporter_uid: str) -> str | None:
    if _should_use_local():
        return local_store.get_fcm_token(reporter_uid)
    try:
        db = _get_db()
        token_doc = db.collection("fcm_tokens").document(reporter_uid).get()
        if not token_doc.exists:
            return None
        return (token_doc.to_dict() or {}).get("fcm_token")
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return local_store.get_fcm_token(reporter_uid)
        raise


def notify_reporter_status_updated(
    reporter_uid: str,
    report_id: str,
    status: str,
    report_type: str,
    content: str,
) -> None:
    status_label = "Diverifikasi" if status == "verified" else "Ditolak"
    preview = content[:80] + "..." if len(content) > 80 else content
    title = f"Laporan Anda {status_label}"
    body = f"Tipe: {report_type}. {preview}"

    try:
        add_user_notification(
            uid=reporter_uid,
            title=title,
            body=body,
            notif_type="report_status_updated",
            extra={"report_id": report_id, "status": status},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to store reporter inbox notification: %s", exc)

    try:
        fcm_token = _get_reporter_token(reporter_uid)
        if not fcm_token:
            return

        msg = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(title=title, body=body),
            data={
                "type": "report_status_updated",
                "report_id": report_id,
                "status": status,
            },
        )
        messaging.send(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to notify report owner: %s", exc)
