"""
Persist hasil analisis (riwayat + notifikasi) tanpa memblokir event loop.
"""
from typing import Optional

import asyncio

from app.core.logging import get_logger
from app.models.analyze_schema import AnalysisResult
from app.repositories.firestore_repository import add_user_notification, save_scan_history

logger = get_logger(__name__)


async def persist_analysis_result(
    user_id: Optional[str],
    result: AnalysisResult,
    *,
    high_risk_title: str,
) -> AnalysisResult:
    """Simpan riwayat di thread pool agar I/O sync tidak menahan response AI."""
    if not user_id:
        logger.info("Skip simpan riwayat: user belum login")
        return result

    try:
        payload = result.model_dump(mode="json")
        scan_id = await asyncio.to_thread(save_scan_history, user_id, payload)
        result.scan_id = scan_id
        if result.risk_level.value == "high":
            await asyncio.to_thread(
                add_user_notification,
                user_id,
                high_risk_title,
                result.input_summary[:120],
                "security_alert",
                {"scan_id": scan_id, "risk_level": result.risk_level.value},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gagal menyimpan scan_history: %s", exc)

    return result
