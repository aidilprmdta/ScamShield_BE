"""
Send FCM push notification to all admin devices when a new report is submitted.
"""
from firebase_admin import messaging

from app.core.logging import get_logger
from app.repositories.firestore_repository import _get_db

logger = get_logger(__name__)


def notify_admins_new_report(report_id: str, report_type: str, content: str) -> None:
    """
    Fetch all admin FCM tokens from Firestore and send a notification.
    Admin users are identified by documents in the 'admin_users' collection.
    Each admin's FCM token is stored in 'fcm_tokens/{uid}'.
    """
    try:
        db = _get_db()

        admin_docs = db.collection("admin_users").stream()
        admin_uids = [doc.id for doc in admin_docs]

        if not admin_uids:
            return

        tokens = []
        for uid in admin_uids:
            token_doc = db.collection("fcm_tokens").document(uid).get()
            if token_doc.exists:
                fcm_token = token_doc.to_dict().get("fcm_token")
                if fcm_token:
                    tokens.append(fcm_token)

        if not tokens:
            return

        preview = content[:80] + "..." if len(content) > 80 else content
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=f"Laporan Baru [{report_type}]",
                body=preview,
            ),
            data={
                "type": "new_report",
                "report_id": report_id,
            },
            tokens=tokens,
        )

        response = messaging.send_each_for_multicast(message)
        logger.info("Admin notification sent: %d success, %d failure",
                    response.success_count, response.failure_count)

    except Exception as e:
        logger.warning("Failed to notify admins: %s", e)
