"""
Gabungan seluruh endpoint versi v1.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    analyze_chat,
    analyze_link,
    analyze_qr,
    education,
    history,
    report,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(analyze_chat.router, tags=["Analysis"])
api_router.include_router(analyze_link.router, tags=["Analysis"])
api_router.include_router(analyze_qr.router, tags=["Analysis"])
api_router.include_router(history.router, tags=["History"])
api_router.include_router(report.router, tags=["Community Report"])
api_router.include_router(education.router, tags=["Education"])
