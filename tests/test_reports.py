"""
Tes alur laporan komunitas (submit + list user/admin) dengan local store.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_admin_user, get_current_user, get_optional_user
from app.main import app
from app.repositories import local_store
from app.repositories import firestore_repository as fr

client = TestClient(app)


async def _user() -> str:
    return "user_report_1"


async def _admin() -> str:
    return "admin_report_1"


def setup_function() -> None:
    fr._use_local_fallback = True
    with local_store._LOCK:
        data = local_store._ensure_store()
        data["community_reports"] = {}
        data["admin_users"] = {"admin_report_1": {"email": "admin@test.com", "role": "admin"}}
        local_store._write(data)


def test_submit_and_list_my_reports():
    app.dependency_overrides[get_optional_user] = _user
    app.dependency_overrides[get_current_user] = _user
    try:
        with patch("app.api.v1.endpoints.report.notify_admins_new_report"):
            submit = client.post(
                "/api/v1/report",
                json={"type": "chat", "content": "SMS undian palsu", "note": "dari WA"},
                headers={"Authorization": "Bearer x"},
            )
        assert submit.status_code == 200
        body = submit.json()
        assert body["success"] is True
        report_id = body["data"]["report_id"]

        listed = client.get("/api/v1/reports/mine", headers={"Authorization": "Bearer x"})
        assert listed.status_code == 200
        data = listed.json()["data"]
        assert len(data) == 1
        assert data[0]["report_id"] == report_id
        assert data[0]["verified_status"] == "pending"

        detail = client.get(f"/api/v1/reports/{report_id}", headers={"Authorization": "Bearer x"})
        assert detail.status_code == 200
        assert detail.json()["data"]["content"] == "SMS undian palsu"
    finally:
        app.dependency_overrides.clear()


def test_admin_verify_report():
    app.dependency_overrides[get_optional_user] = _user
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_admin_user] = _admin
    try:
        with patch("app.api.v1.endpoints.report.notify_admins_new_report"):
            submit = client.post(
                "/api/v1/report",
                json={"type": "link", "content": "http://phish.example"},
                headers={"Authorization": "Bearer x"},
            )
        report_id = submit.json()["data"]["report_id"]

        with patch("app.api.v1.endpoints.admin_reports.notify_reporter_status_updated"):
            with patch("app.api.v1.endpoints.admin_reports._admin_email", return_value="admin@test.com"):
                updated = client.patch(
                    f"/api/v1/admin/reports/{report_id}",
                    json={"status": "verified"},
                    headers={"Authorization": "Bearer admin"},
                )
        assert updated.status_code == 200
        assert "verified" in updated.json()["message"]

        admin_list = client.get("/api/v1/admin/reports", headers={"Authorization": "Bearer admin"})
        assert admin_list.status_code == 200
        items = admin_list.json()["data"]
        assert any(i["report_id"] == report_id and i["verified_status"] == "verified" for i in items)

        mine = client.get("/api/v1/reports/mine", headers={"Authorization": "Bearer x"})
        assert mine.json()["data"][0]["verified_status"] == "verified"
    finally:
        app.dependency_overrides.clear()
