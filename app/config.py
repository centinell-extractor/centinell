# app/config.py
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ENV_FILE = os.getenv("CENTINELL_ENV_FILE", ".env.dev")
if not Path(ENV_FILE).exists():
    ENV_FILE = ".env"

load_dotenv(dotenv_path=ENV_FILE, override=True)
logger.info("Cargando entorno desde %s", ENV_FILE)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL no está definido en el archivo de entorno activo: {ENV_FILE}")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(f"OPENAI_API_KEY no está definida en el archivo de entorno activo: {ENV_FILE}")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not JWT_SECRET_KEY or JWT_SECRET_KEY == "change-me-in-production":
    _debug = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
    if _debug:
        JWT_SECRET_KEY = "dev-only-insecure-secret-do-not-use-in-production"
        logger.warning("JWT_SECRET_KEY no configurado. Usando secreto de desarrollo. NO usar en producción.")
    else:
        raise RuntimeError("JWT_SECRET_KEY debe estar configurado con un valor seguro en producción.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 10080))

BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
BOOTSTRAP_ADMIN_NAME = os.getenv("BOOTSTRAP_ADMIN_NAME", "Admin Global").strip()

# Límites de producción para uso masivo
MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", 5))
MAX_DOCUMENT_SIZE_BYTES = MAX_DOCUMENT_SIZE_MB * 1024 * 1024

LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", 120))
LLM_MAX_TIMEOUT_SECONDS = 300  # Máximo permitido
LLM_RETRY_ATTEMPTS = min(int(os.getenv("LLM_RETRY_ATTEMPTS", 3)), 10)
LLM_RETRY_DELAY_SECONDS = int(os.getenv("LLM_RETRY_DELAY_SECONDS", 1))

# Concurrencia
MAX_CONCURRENT_EXTRACTIONS = int(os.getenv("MAX_CONCURRENT_EXTRACTIONS", 10))

DOCUMENT_STORAGE_DIR = os.getenv("DOCUMENT_STORAGE_DIR", "storage/documents").strip()

# OCR fallback para PDFs escaneados
OCR_FALLBACK_ENABLED = os.getenv("OCR_FALLBACK_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OCR_MIN_TEXT_CHARS = int(os.getenv("OCR_MIN_TEXT_CHARS", 80))
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "spa+eng")
OCR_DPI = int(os.getenv("OCR_DPI", 400))
OCR_MIN_NATIVE_QUALITY = float(os.getenv("OCR_MIN_NATIVE_QUALITY", 0.45))
OCR_QUALITY_MARGIN = float(os.getenv("OCR_QUALITY_MARGIN", 0.05))
OCR_PREPROCESS_ENABLED = os.getenv("OCR_PREPROCESS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OCR_PREPROCESS_UPSCALE = float(os.getenv("OCR_PREPROCESS_UPSCALE", 1.0))
OCR_PREPROCESS_BIN_THRESHOLD = int(os.getenv("OCR_PREPROCESS_BIN_THRESHOLD", 170))
OCR_PREPROCESS_BIN_THRESHOLDS = os.getenv("OCR_PREPROCESS_BIN_THRESHOLDS", "130,160,190")
OCR_TESSERACT_PSMS = os.getenv("OCR_TESSERACT_PSMS", "6,3,11")
OCR_USE_VISION_API = os.getenv("OCR_USE_VISION_API", "false").lower() in {"1", "true", "yes", "on"}
OCR_TESSERACT_OEM = int(os.getenv("OCR_TESSERACT_OEM", 1))
OCR_TESSERACT_CALL_TIMEOUT_SECONDS = float(
    os.getenv("OCR_TESSERACT_CALL_TIMEOUT_SECONDS", 8)
)
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", 120))
OCR_FORCE_ALL_PAGES = os.getenv("OCR_FORCE_ALL_PAGES", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
POPPLER_PATH = os.getenv("POPPLER_PATH", "").strip()

# Email (SMTP opcional — si no está configurado, el token se escribe en el log)
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@centinell.app").strip()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").strip().rstrip("/")
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", 60))
