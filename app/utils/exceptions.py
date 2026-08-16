"""
Exception kustom untuk aplikasi + handler agar response error konsisten.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


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
    """Error saat memanggil layanan eksternal (Gemini, URLhaus, Firestore)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Layanan eksternal sedang tidak tersedia. Silakan coba lagi."


class OcrLowConfidenceError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Kualitas teks hasil OCR terlalu rendah, mohon masukkan teks secara manual."


def _error_payload(error_type: str, message: str) -> dict:
    return {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def _first_validation_message(exc: RequestValidationError) -> str:
    try:
        errors = exc.errors()
        if not errors:
            return "Input tidak valid."
        first = errors[0]
        loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        msg = str(first.get("msg") or "Input tidak valid.")
        if loc:
            return f"{loc}: {msg}"
        return msg
    except Exception:  # noqa: BLE001
        return "Input tidak valid."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.__class__.__name__, exc.message),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_payload("ValidationAppError", _first_validation_message(exc)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Terjadi kesalahan."
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload("HTTPException", message),
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error pada %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                "InternalServerError",
                "Terjadi kesalahan pada server. Silakan coba lagi nanti.",
            ),
        )
