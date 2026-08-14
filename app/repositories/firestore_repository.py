"""
Layer akses data ke Firestore (via firebase-admin), sesuai struktur koleksi
yang didefinisikan di PRD §16.
Jika Firestore tidak tersedia (API disabled / belum dikonfigurasi),
otomatis fallback ke local_store (JSON file) agar riwayat & notifikasi tetap jalan.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core import exceptions as google_exceptions

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories import local_store
from app.utils.exceptions import UpstreamServiceError

logger = get_logger(__name__)

_db: Optional["firestore.Client"] = None
_use_local_fallback: Optional[bool] = None

SCAN_HISTORY_COLLECTION = "scan_history"
COMMUNITY_REPORTS_COLLECTION = "community_reports"
EDUCATION_CONTENT_COLLECTION = "education_content"
USER_EDUCATION_PROGRESS_COLLECTION = "user_education_progress"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_service_account_path(raw: str) -> str:
    path = Path(raw.strip())
    if path.is_file():
        return str(path)
    candidate = BACKEND_ROOT / raw.strip()
    if candidate.is_file():
        return str(candidate)
    return raw.strip()


def init_firebase() -> None:
    """Inisialisasi Firebase Admin SDK sekali saat startup aplikasi."""
    settings = get_settings()
    if firebase_admin._apps:
        return
    if not settings.firebase_service_account_json:
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON tidak dikonfigurasi — "
            "menggunakan penyimpanan lokal untuk history/report/notification."
        )
        return
    try:
        raw = settings.firebase_service_account_json
        if raw.strip().startswith("{"):
            cred_dict = json.loads(raw)
            cred = credentials.Certificate(cred_dict)
        else:
            cred = credentials.Certificate(_resolve_service_account_path(raw))
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK berhasil diinisialisasi.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal inisialisasi Firebase Admin SDK: %s", exc)


def _mark_local_fallback(reason: Exception) -> None:
    global _use_local_fallback
    if _use_local_fallback is not True:
        logger.warning(
            "Firestore tidak tersedia (%s). Fallback ke penyimpanan lokal: %s",
            type(reason).__name__,
            reason,
        )
    _use_local_fallback = True


def _is_firestore_unavailable(exc: Exception) -> bool:
    msg = str(exc).lower()
    if isinstance(exc, (google_exceptions.PermissionDenied, google_exceptions.NotFound, google_exceptions.FailedPrecondition)):
        return True
    return any(
        token in msg
        for token in (
            "service_disabled",
            "firestore api has not been used",
            "cloud firestore api",
            "does not exist",
            "404",
            "403",
        )
    )


def _get_db() -> "firestore.Client":
    global _db
    if not firebase_admin._apps:
        raise UpstreamServiceError("Firestore belum dikonfigurasi di server.")
    if _db is None:
        _db = firestore.client()
    return _db


def _should_use_local() -> bool:
    if _use_local_fallback is True:
        return True
    if not firebase_admin._apps:
        return True
    return False


def _normalize_history_doc(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    scan_id = out.get("scan_id") or out.get("scanId")
    if scan_id:
        out["scan_id"] = scan_id
        out["scanId"] = scan_id
    return out


# ---------------- scan_history ----------------

def save_scan_history(user_id: Optional[str], analysis: dict[str, Any]) -> str:
    if _should_use_local():
        return local_store.save_scan_history(user_id, analysis)
    try:
        db = _get_db()
        scan_id = str(uuid.uuid4())
        doc = {**analysis, "scan_id": scan_id, "scanId": scan_id, "userId": user_id}
        db.collection(SCAN_HISTORY_COLLECTION).document(scan_id).set(doc)
        return scan_id
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return local_store.save_scan_history(user_id, analysis)
        raise UpstreamServiceError(f"Gagal menyimpan riwayat: {exc}") from exc


def list_scan_history(
    user_id: str, limit: int = 20, start_after_id: Optional[str] = None
) -> list[dict[str, Any]]:
    if _should_use_local():
        return [_normalize_history_doc(d) for d in local_store.list_scan_history(user_id, limit, start_after_id)]
    try:
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

        return [_normalize_history_doc(d.to_dict() or {}) for d in query.stream()]
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return [
                _normalize_history_doc(d)
                for d in local_store.list_scan_history(user_id, limit, start_after_id)
            ]
        raise UpstreamServiceError(f"Gagal memuat riwayat: {exc}") from exc


def delete_scan_history(user_id: str, scan_id: str) -> bool:
    if _should_use_local():
        return local_store.delete_scan_history(user_id, scan_id)
    try:
        db = _get_db()
        ref = db.collection(SCAN_HISTORY_COLLECTION).document(scan_id)
        doc = ref.get()
        if not doc.exists or (doc.to_dict() or {}).get("userId") != user_id:
            return False
        ref.delete()
        return True
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return local_store.delete_scan_history(user_id, scan_id)
        raise UpstreamServiceError(f"Gagal menghapus riwayat: {exc}") from exc


# ---------------- community_reports ----------------

def save_community_report(user_id: Optional[str], report: dict[str, Any]) -> str:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    
    if _should_use_local():
        logger.warning("Using local store fallback for community_report")
        return local_store.save_community_report(user_id, report)
    try:
        db = _get_db()
        report_id = str(uuid.uuid4())
        doc = {**report, "reportId": report_id, "reportedBy": user_id}
        logger.info(f"Saving community_report to Firestore: report_id={report_id}, user_id={user_id}")
        db.collection(COMMUNITY_REPORTS_COLLECTION).document(report_id).set(doc)
        logger.info(f"Successfully saved community_report: {report_id}")
        return report_id
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to save community_report to Firestore: {exc}", exc_info=True)
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            logger.warning("Falling back to local store")
            return local_store.save_community_report(user_id, report)
        raise UpstreamServiceError(f"Gagal menyimpan laporan: {exc}") from exc


def _normalize_report_doc(doc_id: str, data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    report_id = out.get("reportId") or out.get("report_id") or doc_id
    out["reportId"] = report_id
    out["report_id"] = report_id
    return out


def list_community_reports(
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if _should_use_local():
        return [
            _normalize_report_doc(d.get("reportId", ""), d)
            for d in local_store.list_community_reports(status_filter, limit)
        ]
    try:
        db = _get_db()
        query = db.collection(COMMUNITY_REPORTS_COLLECTION)
        if status_filter:
            query = query.where("verifiedStatus", "==", status_filter)
        try:
            docs = list(
                query.order_by("createdAt", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
        except Exception:
            # Index belum siap: ambil lalu sort di memori
            docs = list(query.limit(limit * 2).stream())
            docs.sort(
                key=lambda d: (d.to_dict() or {}).get("createdAt") or "",
                reverse=True,
            )
            docs = docs[:limit]
        return [_normalize_report_doc(doc.id, doc.to_dict() or {}) for doc in docs]
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return [
                _normalize_report_doc(d.get("reportId", ""), d)
                for d in local_store.list_community_reports(status_filter, limit)
            ]
        raise UpstreamServiceError(f"Gagal memuat laporan: {exc}") from exc


def list_user_reports(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    if _should_use_local():
        return [
            _normalize_report_doc(d.get("reportId", ""), d)
            for d in local_store.list_user_reports(user_id, limit)
        ]
    try:
        db = _get_db()
        query = db.collection(COMMUNITY_REPORTS_COLLECTION).where("reportedBy", "==", user_id)
        try:
            docs = list(
                query.order_by("createdAt", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
        except Exception:
            docs = list(query.limit(limit * 2).stream())
            docs.sort(
                key=lambda d: (d.to_dict() or {}).get("createdAt") or "",
                reverse=True,
            )
            docs = docs[:limit]
        return [_normalize_report_doc(doc.id, doc.to_dict() or {}) for doc in docs]
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return [
                _normalize_report_doc(d.get("reportId", ""), d)
                for d in local_store.list_user_reports(user_id, limit)
            ]
        raise UpstreamServiceError(f"Gagal memuat laporan user: {exc}") from exc


def get_community_report(report_id: str) -> Optional[dict[str, Any]]:
    if _should_use_local():
        doc = local_store.get_community_report(report_id)
        return _normalize_report_doc(report_id, doc) if doc else None
    try:
        db = _get_db()
        snap = db.collection(COMMUNITY_REPORTS_COLLECTION).document(report_id).get()
        if not snap.exists:
            return None
        return _normalize_report_doc(snap.id, snap.to_dict() or {})
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            doc = local_store.get_community_report(report_id)
            return _normalize_report_doc(report_id, doc) if doc else None
        raise UpstreamServiceError(f"Gagal memuat detail laporan: {exc}") from exc


def update_community_report(report_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    if _should_use_local():
        doc = local_store.update_community_report(report_id, updates)
        return _normalize_report_doc(report_id, doc) if doc else None
    try:
        db = _get_db()
        ref = db.collection(COMMUNITY_REPORTS_COLLECTION).document(report_id)
        snap = ref.get()
        if not snap.exists:
            return None
        ref.update(updates)
        updated = snap.to_dict() or {}
        updated.update(updates)
        return _normalize_report_doc(report_id, updated)
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            doc = local_store.update_community_report(report_id, updates)
            return _normalize_report_doc(report_id, doc) if doc else None
        raise UpstreamServiceError(f"Gagal memperbarui laporan: {exc}") from exc


def count_community_reports(status_filter: Optional[str] = None) -> int:
    return len(list_community_reports(status_filter=status_filter, limit=500))


def count_user_reports(user_id: str, status_filter: Optional[str] = None) -> int:
    items = list_user_reports(user_id, limit=500)
    if status_filter:
        items = [d for d in items if d.get("verifiedStatus") == status_filter]
    return len(items)


# ---------------- fcm tokens ----------------

def save_fcm_token(uid: str, fcm_token: str) -> None:
    if _should_use_local():
        local_store.save_fcm_token(uid, fcm_token)
        return
    try:
        db = _get_db()
        db.collection("fcm_tokens").document(uid).set(
            {"fcm_token": fcm_token, "uid": uid},
            merge=True,
        )
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            local_store.save_fcm_token(uid, fcm_token)
            return
        raise UpstreamServiceError(f"Gagal menyimpan token notifikasi: {exc}") from exc


def add_user_notification(
    uid: str,
    title: str,
    body: str,
    notif_type: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Selalu simpan ke local store agar inbox notifikasi tersedia tanpa Firestore."""
    return local_store.add_notification(uid, title, body, notif_type, extra)


def list_user_notifications(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    return local_store.list_notifications(uid, limit)


def mark_user_notification_read(uid: str, notif_id: str) -> bool:
    return local_store.mark_notification_read(uid, notif_id)


# ---------------- education_content ----------------

def list_education_content(category: Optional[str] = None) -> list[dict[str, Any]]:
    if _should_use_local():
        return local_store.list_education_content(category)
    try:
        db = _get_db()
        query = db.collection(EDUCATION_CONTENT_COLLECTION)
        if category:
            query = query.where("category", "==", category)
        query = query.order_by("publishedAt", direction=firestore.Query.DESCENDING)
        return [d.to_dict() | {"id": d.id} for d in query.stream()]
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return local_store.list_education_content(category)
        raise UpstreamServiceError(f"Gagal memuat edukasi: {exc}") from exc


def get_education_content(content_id: str) -> Optional[dict[str, Any]]:
    if _should_use_local():
        return local_store.get_education_content(content_id)
    try:
        db = _get_db()
        doc = db.collection(EDUCATION_CONTENT_COLLECTION).document(content_id).get()
        if not doc.exists:
            return None
        return doc.to_dict() | {"id": doc.id}
    except Exception as exc:  # noqa: BLE001
        if _is_firestore_unavailable(exc):
            _mark_local_fallback(exc)
            return local_store.get_education_content(content_id)
        raise UpstreamServiceError(f"Gagal memuat detail edukasi: {exc}") from exc


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
