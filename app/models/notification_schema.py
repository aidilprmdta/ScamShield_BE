from pydantic import BaseModel


class RegisterFcmTokenRequest(BaseModel):
    fcm_token: str
