"""
Entry point FastAPI — ScamShield AI Backend.
Menjalankan: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.rate_limit import setup_rate_limiting
from app.repositories.firestore_repository import init_firebase
from app.utils.exceptions import register_exception_handlers

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ScamShield AI Backend (env=%s)", get_settings().environment)
    init_firebase()
    yield
    logger.info("Shutting down ScamShield AI Backend")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ScamShield AI — Backend API",
        description=(
            "REST API untuk orkestrasi AI Analysis (Gemini), pengecekan tautan "
            "(Google Safe Browsing + custom logic), riwayat deteksi, pelaporan "
            "komunitas, dan konten edukasi literasi digital."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    setup_rate_limiting(app)
    app.include_router(api_router)

    @app.get("/", tags=["Health"], summary="Health check")
    async def root() -> dict:
        return {"success": True, "service": "ScamShield AI Backend", "status": "ok"}

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health() -> dict:
        return {"success": True, "status": "healthy"}

    return app


app = create_app()
