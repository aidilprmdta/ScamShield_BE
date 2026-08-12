from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email pengguna")
    password: str = Field(..., min_length=6, description="Password pengguna (min 6 karakter)")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email pengguna")
    password: str = Field(..., description="Password pengguna")


class AuthTokens(BaseModel):
    # Format mengikuti respons Firebase Identity Toolkit supaya FE gampang pakai lagi.
    idToken: str
    refreshToken: str
    localId: str
    email: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool = True
    data: AuthTokens


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., description="Google ID token dari Credential Manager / Google Sign-In")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Firebase refresh token")


class AuthMeData(BaseModel):
    uid: str
    email: Optional[str] = None
    admin: bool = False


class AuthMeResponse(BaseModel):
    success: bool = True
    data: AuthMeData

