"""
Konfigurasi aplikasi — dibaca dari environment variables (.env).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # Safe Browsing
    google_safe_browsing_api_key: str = ""

    # Firebase
    firebase_service_account_json: str = ""
    # Firebase Auth (Identity Toolkit) - harus Web API key project yang sama dengan app
    firebase_web_api_key: str = ""
    # Key cadangan jika user tersimpan di project Firebase lama
    firebase_web_api_key_fallback: str = ""
    firebase_project_id: str = "scamshieldai-9de2170b"
    firebase_project_ids: str = "scamshieldai-9de2170b,scamshield-ai-2026"
    # Admin tanpa Firebase custom claim (comma-separated)
    admin_uids: str = ""
    admin_emails: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    allowed_origins: str = "*"

    # Misc
    analysis_cache_ttl_seconds: int = 3600
    http_timeout_seconds: int = 10

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
