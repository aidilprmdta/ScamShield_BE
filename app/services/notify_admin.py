"""
Send FCM push notification to all admin devices when a new report is submitted.
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


def _collect_admin_tokens() -> list[str]:
    if _should_use_local():
        tokens = []
        for uid in local_store.list_admin_uids():
            token = local_store.get_fcm_token(uid)
            if token:
                tokens.append(token)
        return tokens

    try:
        db = _get_db()
        admin_uids = [doc.id for doc in db.collection("admin_users").stream()]
        tokens = []
        for uid in admin_uids:
            token_doc = db.collection("fcm_tokens").document(uid).get()
            if token_doc.exists:
                fcm_token = (token_doc.to_dict() or {}).get("fcm_token")
                if fcm_token:
                    tokens.append(fcm_token)
        return tokens
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            tokens = []
            for uid in local_store.list_admin_uids():
                token = local_store.get_fcm_token(uid)
                if token:
                    tokens.append(token)
            return tokens
        raise


def notify_admins_new_report(report_id: str, report_type: str, content: str) -> None:
    preview = content[:80] + "..." if len(content) > 80 else content
    title = f"Laporan Baru [{report_type}]"

    try:
        for uid in local_store.list_admin_uids():
            add_user_notification(
                uid=uid,
                title=title,
                body=preview,
                notif_type="new_report",
                extra={"report_id": report_id},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to store admin inbox notification: %s", e)

    try:
        tokens = _collect_admin_tokens()
        if not tokens:
            return

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=preview),
            data={"type": "new_report", "report_id": report_id},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(
            "Admin notification sent: %d success, %d failure",
            response.success_count,
            response.failure_count,
        )
    except Exception as e:
        logger.warning("Failed to notify admins: %s", e)
