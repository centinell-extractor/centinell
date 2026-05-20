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
