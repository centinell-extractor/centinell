# app/main.py
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import prompt_configs
from app.routers import test_template
from app.routers import extract_test
from app.routers import extract
from app.routers import extractions
from app.routers import documents
from app.routers import collections

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Centinell - Extraction Service")

# CORS para acceso desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configurar dominios específicos en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Incluir routers
app.include_router(prompt_configs.router)
app.include_router(test_template.router)
app.include_router(extract_test.router)
app.include_router(extract.router)
app.include_router(extractions.router)
app.include_router(documents.router)
app.include_router(collections.router)


@app.get("/")
async def root():
    return FileResponse(static_dir / "index.html")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(static_dir / "favicon.svg", media_type="image/svg+xml")

# Global exception handler para errores no controlados
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


@app.on_event("startup")
async def startup_event():
    logger.info("Aplicación iniciada correctamente")