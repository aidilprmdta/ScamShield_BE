"""
Layer akses data ke Firestore (via firebase-admin), sesuai struktur koleksi
yang didefinisikan di PRD §16:
- scan_history/{scanId}
- community_reports/{reportId}
- education_content/{contentId}
- user_education_progress/{userId}/items/{contentId}
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.exceptions import UpstreamServiceError

logger = get_logger(__name__)

_db: Optional["firestore.Client"] = None

SCAN_HISTORY_COLLECTION = "scan_history"
COMMUNITY_REPORTS_COLLECTION = "community_reports"
EDUCATION_CONTENT_COLLECTION = "education_content"
USER_EDUCATION_PROGRESS_COLLECTION = "user_education_progress"


def init_firebase() -> None:
    """Inisialisasi Firebase Admin SDK sekali saat startup aplikasi."""
    settings = get_settings()
    if firebase_admin._apps:
        return
    if not settings.firebase_service_account_json:
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON tidak dikonfigurasi — "
            "fitur history/report/education akan gagal sampai dikonfigurasi."
        )
        return
    try:
        raw = settings.firebase_service_account_json
        # Mendukung: path file JSON, ATAU isi JSON langsung sebagai string
        if raw.strip().startswith("{"):
            cred_dict = json.loads(raw)
            cred = credentials.Certificate(cred_dict)
        else:
            cred = credentials.Certificate(raw)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK berhasil diinisialisasi.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal inisialisasi Firebase Admin SDK: %s", exc)


def _get_db() -> "firestore.Client":
    global _db
    if not firebase_admin._apps:
        raise UpstreamServiceError("Firestore belum dikonfigurasi di server.")
    if _db is None:
        _db = firestore.client()
    return _db


# ---------------- scan_history ----------------

def save_scan_history(user_id: Optional[str], analysis: dict[str, Any]) -> str:
    db = _get_db()
    scan_id = str(uuid.uuid4())
    doc = {**analysis, "scanId": scan_id, "userId": user_id}
    db.collection(SCAN_HISTORY_COLLECTION).document(scan_id).set(doc)
    return scan_id


def list_scan_history(
    user_id: str, limit: int = 20, start_after_id: Optional[str] = None
) -> list[dict[str, Any]]:
    db = _get_db()
    query = (
        db.collection(SCAN_HISTORY_COLLECTION)
        .where("userId", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    if start_after_id:
        start_doc = db.collection(SCAN_HISTORY_COLLECTION).document(start_after_id).get()
        if start_doc.exists:
            query = query.start_after(start_doc)

    return [d.to_dict() for d in query.stream()]


def delete_scan_history(user_id: str, scan_id: str) -> bool:
    db = _get_db()
    ref = db.collection(SCAN_HISTORY_COLLECTION).document(scan_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("userId") != user_id:
        return False
    ref.delete()
    return True


# ---------------- community_reports ----------------

def save_community_report(user_id: Optional[str], report: dict[str, Any]) -> str:
    db = _get_db()
    report_id = str(uuid.uuid4())
    doc = {**report, "reportId": report_id, "reportedBy": user_id}
    db.collection(COMMUNITY_REPORTS_COLLECTION).document(report_id).set(doc)
    return report_id


# ---------------- education_content ----------------

def list_education_content(category: Optional[str] = None) -> list[dict[str, Any]]:
    db = _get_db()
    query = db.collection(EDUCATION_CONTENT_COLLECTION)
    if category:
        query = query.where("category", "==", category)
    query = query.order_by("publishedAt", direction=firestore.Query.DESCENDING)
    return [d.to_dict() | {"id": d.id} for d in query.stream()]


def get_education_content(content_id: str) -> Optional[dict[str, Any]]:
    db = _get_db()
    doc = db.collection(EDUCATION_CONTENT_COLLECTION).document(content_id).get()
    if not doc.exists:
        return None
    return doc.to_dict() | {"id": doc.id}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
