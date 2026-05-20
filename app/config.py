# app/config.py
import os
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está definido en el archivo .env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY no está definida en el archivo .env")

# Límites de producción para uso masivo
MAX_DOCUMENT_SIZE_MB = int(os.getenv("MAX_DOCUMENT_SIZE_MB", 5))
MAX_DOCUMENT_SIZE_BYTES = MAX_DOCUMENT_SIZE_MB * 1024 * 1024

LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", 120))
LLM_MAX_TIMEOUT_SECONDS = 300  # Máximo permitido
LLM_RETRY_ATTEMPTS = int(os.getenv("LLM_RETRY_ATTEMPTS", 3))
LLM_RETRY_DELAY_SECONDS = int(os.getenv("LLM_RETRY_DELAY_SECONDS", 1))

# Concurrencia
MAX_CONCURRENT_EXTRACTIONS = int(os.getenv("MAX_CONCURRENT_EXTRACTIONS", 10))

# OCR fallback para PDFs escaneados
OCR_FALLBACK_ENABLED = os.getenv("OCR_FALLBACK_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OCR_MIN_TEXT_CHARS = int(os.getenv("OCR_MIN_TEXT_CHARS", 80))
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "spa+eng")
OCR_DPI = int(os.getenv("OCR_DPI", 300))
OCR_MIN_NATIVE_QUALITY = float(os.getenv("OCR_MIN_NATIVE_QUALITY", 0.45))
OCR_QUALITY_MARGIN = float(os.getenv("OCR_QUALITY_MARGIN", 0.05))
OCR_FORCE_ALL_PAGES = os.getenv("OCR_FORCE_ALL_PAGES", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
POPPLER_PATH = os.getenv("POPPLER_PATH", "").strip()
