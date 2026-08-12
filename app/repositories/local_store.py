"""
Penyimpanan lokal (JSON file) sebagai fallback saat Firestore tidak tersedia.
Digunakan untuk development / demo ketika Cloud Firestore API belum diaktifkan.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_STORE_PATH = _DATA_DIR / "local_store.json"

_DEFAULT: dict[str, Any] = {
    "scan_history": {},
    "community_reports": {},
    "fcm_tokens": {},
    "admin_users": {},
    "education_content": {},
    "notifications": {},
}


def _ensure_store() -> dict[str, Any]:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.exists():
        _write(_DEFAULT.copy())
        return {k: dict(v) for k, v in _DEFAULT.items()}
    try:
        with _STORE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}
    for key, default in _DEFAULT.items():
        data.setdefault(key, dict(default) if isinstance(default, dict) else default)
    return data


def _write(data: dict[str, Any]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(_STORE_PATH)


def save_scan_history(user_id: Optional[str], analysis: dict[str, Any]) -> str:
    with _LOCK:
        data = _ensure_store()
        scan_id = str(uuid.uuid4())
        doc = {**analysis, "scan_id": scan_id, "scanId": scan_id, "userId": user_id}
        data["scan_history"][scan_id] = doc
        _write(data)
        return scan_id


def list_scan_history(
    user_id: str, limit: int = 20, start_after_id: Optional[str] = None
) -> list[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        items = [
            dict(doc)
            for doc in data["scan_history"].values()
            if doc.get("userId") == user_id
        ]
    items.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    if start_after_id:
        idx = next((i for i, d in enumerate(items) if d.get("scanId") == start_after_id or d.get("scan_id") == start_after_id), None)
        items = items[idx + 1 :] if idx is not None else items
    return items[:limit]


def delete_scan_history(user_id: str, scan_id: str) -> bool:
    with _LOCK:
        data = _ensure_store()
        doc = data["scan_history"].get(scan_id)
        if not doc or doc.get("userId") != user_id:
            return False
        del data["scan_history"][scan_id]
        _write(data)
        return True


def save_community_report(user_id: Optional[str], report: dict[str, Any]) -> str:
    with _LOCK:
        data = _ensure_store()
        report_id = str(uuid.uuid4())
        doc = {**report, "reportId": report_id, "reportedBy": user_id}
        data["community_reports"][report_id] = doc
        _write(data)
        return report_id


def save_fcm_token(uid: str, fcm_token: str) -> None:
    with _LOCK:
        data = _ensure_store()
        data["fcm_tokens"][uid] = {"fcm_token": fcm_token, "uid": uid}
        _write(data)


def get_fcm_token(uid: str) -> Optional[str]:
    with _LOCK:
        data = _ensure_store()
        entry = data["fcm_tokens"].get(uid) or {}
        return entry.get("fcm_token")


def add_notification(
    uid: str,
    title: str,
    body: str,
    notif_type: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    with _LOCK:
        data = _ensure_store()
        notif_id = str(uuid.uuid4())
        doc = {
            "id": notif_id,
            "uid": uid,
            "title": title,
            "body": body,
            "type": notif_type,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": extra or {},
        }
        data["notifications"][notif_id] = doc
        _write(data)
        return dict(doc)


def list_notifications(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        items = [dict(d) for d in data["notifications"].values() if d.get("uid") == uid]
    items.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    return items[:limit]


def mark_notification_read(uid: str, notif_id: str) -> bool:
    with _LOCK:
        data = _ensure_store()
        doc = data["notifications"].get(notif_id)
        if not doc or doc.get("uid") != uid:
            return False
        doc["read"] = True
        data["notifications"][notif_id] = doc
        _write(data)
        return True


def list_admin_uids() -> list[str]:
    with _LOCK:
        data = _ensure_store()
        return list(data["admin_users"].keys())


def upsert_admin_user(uid: str, email: str) -> None:
    with _LOCK:
        data = _ensure_store()
        data["admin_users"][uid] = {"email": email, "role": "admin"}
        _write(data)


def list_education_content(category: Optional[str] = None) -> list[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        items = []
        for doc_id, doc in data["education_content"].items():
            if category and doc.get("category") != category:
                continue
            items.append({**doc, "id": doc_id})
        items.sort(key=lambda d: d.get("publishedAt") or "", reverse=True)
        return items


def get_education_content(content_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        doc = data["education_content"].get(content_id)
        if not doc:
            return None
        return {**doc, "id": content_id}


def get_community_report(report_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        return data["community_reports"].get(report_id)


def list_community_reports(status_filter: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        items = list(data["community_reports"].values())
    if status_filter:
        items = [d for d in items if d.get("verifiedStatus") == status_filter or d.get("verified_status") == status_filter]
    items.sort(key=lambda d: d.get("createdAt") or d.get("created_at") or "", reverse=True)
    return items[:limit]


def update_community_report(report_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        doc = data["community_reports"].get(report_id)
        if not doc:
            return None
        doc.update(updates)
        data["community_reports"][report_id] = doc
        _write(data)
        return dict(doc)


def list_user_reports(user_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        data = _ensure_store()
        items = [dict(d) for d in data["community_reports"].values() if d.get("reportedBy") == user_id]
    items.sort(key=lambda d: d.get("createdAt") or "", reverse=True)
    return items
