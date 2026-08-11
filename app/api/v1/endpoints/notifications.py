from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.notification_schema import RegisterFcmTokenRequest
from app.repositories.firestore_repository import _get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/register-token")
async def register_fcm_token(
    request: RegisterFcmTokenRequest,
    uid: str = Depends(get_current_user),
):
    db = _get_db()
    db.collection("fcm_tokens").document(uid).set(
        {"fcm_token": request.fcm_token, "uid": uid},
        merge=True,
    )

    return {"success": True, "message": "Token registered"}
