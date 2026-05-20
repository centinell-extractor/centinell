# app/routers/documents.py
from io import BytesIO
from pathlib import Path
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import (
    MAX_DOCUMENT_SIZE_BYTES,
    OCR_DPI,
    OCR_FALLBACK_ENABLED,
    OCR_FORCE_ALL_PAGES,
    OCR_LANGUAGES,
    OCR_MIN_NATIVE_QUALITY,
    OCR_MIN_TEXT_CHARS,
    OCR_QUALITY_MARGIN,
    POPPLER_PATH,
    TESSERACT_CMD,
)

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


def _extract_pdf_text_native_pages(content: bytes) -> list[str]:
    """
    Extrae texto nativo por página para poder decidir OCR en documentos mixtos.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=400,
            detail="Para procesar PDF instala pypdf: pip install pypdf",
        ) from exc

    reader = PdfReader(BytesIO(content))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def _extract_pdf_text_ocr_pages(content: bytes) -> list[str]:
    """
    Extrae texto OCR por página para comparar contra extracción nativa página a página.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "OCR no disponible. Instala dependencias Python: "
                "pip install pdf2image pytesseract"
            ),
        ) from exc

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    try:
        poppler_path = POPPLER_PATH or None
        images = convert_from_bytes(content, dpi=OCR_DPI, poppler_path=poppler_path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se pudo convertir PDF a imagen para OCR. "
                "En Windows instala Poppler y agrega su bin al PATH."
            ),
        ) from exc

    chunks = []
    for image in images:
        try:
            text = pytesseract.image_to_string(image, lang=OCR_LANGUAGES)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Error ejecutando OCR con Tesseract. "
                    "Verifica que Tesseract este instalado y disponible en PATH."
                ),
            ) from exc
        chunks.append((text or "").strip())

    return chunks


def _should_use_ocr(native_text: str) -> bool:
    """
    Decide si activar OCR cuando el texto embebido es insuficiente.
    """
    cleaned = (native_text or "").strip()
    if len(cleaned) < OCR_MIN_TEXT_CHARS:
        return True
    return _text_quality_score(cleaned) < OCR_MIN_NATIVE_QUALITY


def _text_quality_score(text: str) -> float:
    """
    Estima calidad de texto extraído (0-1): penaliza texto corrupto y caracteres de reemplazo.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return 0.0

    total = len(cleaned)
    printable_ratio = sum(1 for ch in cleaned if ch.isprintable()) / total
    alnum_ratio = sum(1 for ch in cleaned if ch.isalnum()) / total
    replacement_ratio = cleaned.count("\ufffd") / total

    score = (0.55 * printable_ratio) + (0.45 * alnum_ratio) - (1.2 * replacement_ratio)
    return max(0.0, min(1.0, score))


def _pick_best_pdf_text(native_text: str, ocr_text: str) -> str:
    """
    Elige entre texto nativo y OCR priorizando calidad legible.
    """
    native = (native_text or "").strip()
    ocr = (ocr_text or "").strip()

    if not ocr:
        return native
    if not native:
        return ocr

    native_score = _text_quality_score(native)
    ocr_score = _text_quality_score(ocr)

    if ocr_score >= native_score + OCR_QUALITY_MARGIN:
        return ocr

    if ocr_score > native_score and len(ocr) >= int(len(native) * 0.85):
        return ocr

    return native


def _should_use_ocr_on_any_page(native_pages: list[str]) -> bool:
    """
    Activa OCR si al menos una página parece pobre o con extracción deficiente.
    """
    if not native_pages:
        return True

    for page_text in native_pages:
        if _should_use_ocr(page_text):
            return True

    return False


def _combine_best_pdf_pages(native_pages: list[str], ocr_pages: list[str]) -> tuple[str, int]:
    """
    Devuelve texto final combinando mejor opción por página y cuántas páginas usaron OCR.
    """
    max_len = max(len(native_pages), len(ocr_pages))
    merged_pages: list[str] = []
    pages_using_ocr = 0

    for idx in range(max_len):
        native_page = native_pages[idx] if idx < len(native_pages) else ""
        ocr_page = ocr_pages[idx] if idx < len(ocr_pages) else ""
        if OCR_FORCE_ALL_PAGES and ocr_page.strip():
            chosen = ocr_page.strip()
        else:
            chosen = _pick_best_pdf_text(native_page, ocr_page).strip()
        if chosen == (ocr_page or "").strip() and chosen:
            pages_using_ocr += 1
        merged_pages.append(chosen)

    return "\n\n".join(page for page in merged_pages if page).strip(), pages_using_ocr


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
            native_pages = _extract_pdf_text_native_pages(content)
            native_text = "\n\n".join(page for page in native_pages if page).strip()
            text = native_text
            used_ocr = False

            should_run_ocr = OCR_FORCE_ALL_PAGES or _should_use_ocr_on_any_page(native_pages)
            if OCR_FALLBACK_ENABLED and should_run_ocr:
                logger.info(
                    "Documento PDF procesado con OCR por pagina (force_all_pages=%s, chars=%s, score=%.3f).",
                    OCR_FORCE_ALL_PAGES,
                    len(native_text),
                    _text_quality_score(native_text),
                )
                ocr_pages = _extract_pdf_text_ocr_pages(content)
                text, pages_using_ocr = _combine_best_pdf_pages(native_pages, ocr_pages)
                used_ocr = pages_using_ocr > 0

                logger.info(
                    "Seleccion por pagina completada (native_score=%.3f, final_score=%.3f, pages_using_ocr=%s/%s)",
                    _text_quality_score(native_text),
                    _text_quality_score(text),
                    pages_using_ocr,
                    max(len(native_pages), len(ocr_pages)),
                )
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
