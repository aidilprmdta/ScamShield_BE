from pydantic import BaseModel, Field
from typing import Any, Optional


class RegisterFcmTokenRequest(BaseModel):
    fcm_token: str


class NotificationItem(BaseModel):
    id: str
    title: str
    body: str
    type: str
    read: bool = False
    created_at: str
    data: dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    success: bool = True
    data: list[NotificationItem] = Field(default_factory=list)


class MarkNotificationReadResponse(BaseModel):
    success: bool = True
    message: str = "Notifikasi ditandai sudah dibaca."
