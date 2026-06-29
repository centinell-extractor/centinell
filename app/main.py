# app/main.py
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limit import limiter

from sqlalchemy import update

from app.bootstrap import ensure_bootstrap_admin
from app.db.connection import AsyncSessionLocal, init_models
from app.db.models import Document
from app.routers import prompt_configs
from app.routers import extract
from app.routers import extractions
from app.routers import documents
from app.routers import collections
from app.routers import auth
from app.routers import bus
from app.routers import admin
from app.routers import assessments
from app.routers import api_keys
from app.routers import reports
from app.routers import webhooks

# ── Structured logging ────────────────────────────────────────────────────────
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(
    jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
)
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_log_handler]
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación (startup / shutdown)."""
    # init_models crea tablas que falten (safety net para dev).
    # En producción, ejecutar: alembic upgrade head
    _debug = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
    if _debug:
        await init_models()
    else:
        logger.info("Modo producción: omitiendo create_all automático (usar alembic upgrade head)")

    async with AsyncSessionLocal() as session:
        await ensure_bootstrap_admin(session)

    # Documentos que quedaron en "processing" por un crash/reinicio anterior
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Document)
            .where(Document.status == "processing")
            .values(status="failed", ocr_error="Procesamiento interrumpido por reinicio del servidor")
            .returning(Document.id)
        )
        recovered = result.fetchall()
        if recovered:
            await session.commit()
            logger.warning("Recuperados %d documentos atascados en 'processing' → 'failed'", len(recovered))

    logger.info("Aplicación iniciada correctamente")
    yield
    # Espacio para cleanup al apagar (cerrar conexiones externas, etc.)


app = FastAPI(
    title="Centinell - Extraction Service",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — sólo orígenes explícitos (vacío = sólo mismo origen, que es el caso normal)
_raw_origins = os.getenv("CORS_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-BU-ID", "X-API-Key"],
    )


@app.middleware("http")
async def request_id_and_security_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Incluir routers
app.include_router(prompt_configs.router)
app.include_router(extract.router)
app.include_router(extractions.router)
app.include_router(documents.router)
app.include_router(collections.router)
app.include_router(auth.router)
app.include_router(bus.router)
app.include_router(admin.router)
app.include_router(assessments.router)
app.include_router(api_keys.router)
app.include_router(reports.router)
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return FileResponse(static_dir / "landing.html", media_type="text/html; charset=utf-8")


@app.get("/app")
async def console():
    return FileResponse(static_dir / "index.html", media_type="text/html; charset=utf-8")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(static_dir / "favicon.svg", media_type="image/svg+xml")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Error no controlado en {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Error interno del servidor",
            "detail": "Contacte al administrador si el problema persiste"
        },
    )


@app.get("/health", tags=["health"])
async def health_check():
    """
    Healthcheck endpoint para monitoreo y load balancers.
    Devuelve 200 si la app está activa.
    """
    return {
        "status": "healthy",
        "service": "Centinell",
        "version": "1.0.0"
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str):
    return FileResponse(static_dir / "index.html", media_type="text/html; charset=utf-8")
