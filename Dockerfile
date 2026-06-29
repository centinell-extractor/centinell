# ── Stage 1: dependencias ────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Dependencias del sistema necesarias para compilar wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: imagen de producción ───────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# OCR: Tesseract + idiomas + Poppler (pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    poppler-utils \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes Python instalados en el stage anterior
COPY --from=builder /install /usr/local

# Código de la aplicación
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Directorio de storage (se sobreescribe con volumen en producción)
RUN mkdir -p storage/documents

# Usuario sin privilegios
RUN useradd -m -u 1001 centinell && chown -R centinell:centinell /app
USER centinell

EXPOSE 8001

# Arranque: migraciones + servidor
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
