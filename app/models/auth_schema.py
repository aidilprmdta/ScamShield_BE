from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email pengguna")
    password: str = Field(..., min_length=6, description="Password pengguna (min 6 karakter)")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email pengguna")
    password: str = Field(..., min_length=1, description="Password pengguna")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


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
    id_token: str = Field(..., min_length=20, description="Google ID token dari Credential Manager / Google Sign-In")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=8, description="Firebase refresh token")


class AuthMeData(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    admin: bool = False


class AuthMeResponse(BaseModel):
    success: bool = True
    data: AuthMeData


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=50,
        description="Nama tampilan pengguna",
    )
    email: Optional[str] = Field(default=None, description="Email baru (opsional)")


class UpdateProfileResponse(BaseModel):
    success: bool = True
    data: AuthMeData
    message: str = "Profil berhasil diperbarui."


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Kata sandi saat ini")
    new_password: str = Field(..., min_length=6, description="Kata sandi baru (min 6 karakter)")


class ChangePasswordResponse(BaseModel):
    success: bool = True
    data: AuthTokens
    message: str = "Kata sandi berhasil diubah."
