"""
Gabungan seluruh endpoint versi v1.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_reports,
    analyze_chat,
    analyze_link,
    analyze_qr,
    auth,
    education,
    history,
    notifications,
    report,
    user_reports,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(analyze_chat.router, tags=["Analysis"])
api_router.include_router(analyze_link.router, tags=["Analysis"])
api_router.include_router(analyze_qr.router, tags=["Analysis"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(history.router, tags=["History"])
api_router.include_router(report.router, tags=["Community Report"])
api_router.include_router(user_reports.router, tags=["Reports"])
api_router.include_router(education.router, tags=["Education"])
api_router.include_router(notifications.router, tags=["Notifications"])
api_router.include_router(admin_reports.router, tags=["Admin"])
