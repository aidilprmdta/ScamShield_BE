"""
Exception kustom untuk aplikasi + handler agar response error konsisten.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class untuk semua error aplikasi."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_message: str = "Terjadi kesalahan."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Input tidak valid."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Tidak terautentikasi."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Data tidak ditemukan."


class UpstreamServiceError(AppError):
    """Error saat memanggil layanan eksternal (Gemini, Safe Browsing, Firestore)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Layanan eksternal sedang tidak tersedia. Silakan coba lagi."


class OcrLowConfidenceError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Kualitas teks hasil OCR terlalu rendah, mohon masukkan teks secara manual."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "type": "InternalServerError",
                    "message": "Terjadi kesalahan pada server. Silakan coba lagi nanti.",
                },
            },
        )
