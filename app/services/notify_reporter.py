"""
Send FCM notification to report owner when status changes.
"""
from firebase_admin import messaging

from app.core.logging import get_logger
from app.repositories.firestore_repository import _get_db

logger = get_logger(__name__)


def notify_reporter_status_updated(
    reporter_uid: str,
    report_id: str,
    status: str,
    report_type: str,
    content: str,
) -> None:
    try:
        db = _get_db()
        token_doc = db.collection("fcm_tokens").document(reporter_uid).get()
        if not token_doc.exists:
            return

        fcm_token = (token_doc.to_dict() or {}).get("fcm_token")
        if not fcm_token:
            return

        status_label = "Diverifikasi" if status == "verified" else "Ditolak"
        preview = content[:80] + "..." if len(content) > 80 else content
        msg = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(
                title=f"Laporan Anda {status_label}",
                body=f"Tipe: {report_type}. {preview}",
            ),
            data={
                "type": "report_status_updated",
                "report_id": report_id,
                "status": status,
            },
        )
        messaging.send(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to notify report owner: %s", exc)

