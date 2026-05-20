# app/routers/documents.py
from io import BytesIO
from pathlib import Path
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import MAX_DOCUMENT_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _decode_text_bytes(content: bytes) -> str:
    """
    Decodifica bytes de texto intentando UTF-8 y fallback a latin-1.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _extract_pdf_text(content: bytes) -> str:
    """
    Extrae texto de PDF usando pypdf si está disponible.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=400,
            detail="Para procesar PDF instala pypdf: pip install pypdf",
        ) from exc

    reader = PdfReader(BytesIO(content))
    chunks = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        chunks.append(page_text)
    return "\n".join(chunks).strip()


def _extract_docx_text(content: bytes) -> str:
    """
    Extrae texto de DOCX usando python-docx si está disponible.
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise HTTPException(
            status_code=400,
            detail="Para procesar DOCX instala python-docx: pip install python-docx",
        ) from exc

    document = Document(BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs if p.text).strip()


@router.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    """
    Recibe un archivo y devuelve texto plano para reutilizarlo en /extract.
    Soporta txt/md/json/csv/xml/html y, opcionalmente, pdf/docx.
    """
    filename = file.filename or "document"
    suffix = Path(filename).suffix.lower()

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    
    # Validar tamaño del archivo
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        size_mb = MAX_DOCUMENT_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo permitido: {size_mb:.1f} MB"
        )

    try:
        if suffix in {".txt", ".md", ".json", ".csv", ".xml", ".html"}:
            text = _decode_text_bytes(content)
        elif suffix == ".pdf":
            text = _extract_pdf_text(content)
        elif suffix == ".docx":
            text = _extract_docx_text(content)
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Formato no soportado. Usa txt, md, json, csv, xml, html, pdf o docx"
                ),
            )

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto útil del archivo",
            )

        return {
            "filename": filename,
            "content_type": file.content_type,
            "char_count": len(text),
            "text": text,
            "preview": text[:1000],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error procesando archivo {filename}")
        raise HTTPException(
            status_code=400,
            detail=f"Error procesando archivo: {str(e)}"
        ) from e
