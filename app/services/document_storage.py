import hashlib
import logging
from pathlib import Path
from uuid import uuid4

from app.config import DOCUMENT_STORAGE_DIR

logger = logging.getLogger(__name__)


class DocumentStorageService:
    def __init__(self, base_dir: str | None = None) -> None:
        root = base_dir or DOCUMENT_STORAGE_DIR
        self.base_path = Path(root)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, original_filename: str) -> tuple[str, str]:
        suffix = Path(original_filename).suffix.lower()
        generated_name = f"{uuid4()}{suffix}"
        full_path = self.base_path / generated_name
        full_path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        return generated_name, digest  # store only filename, not full path

    def delete(self, storage_key: str) -> None:
        try:
            path = self.resolve(storage_key)
            if path.exists():
                path.unlink()
        except Exception:
            logger.warning("Error eliminando archivo de storage: %s", storage_key, exc_info=True)

    def resolve(self, storage_key: str) -> Path:
        candidate = Path(storage_key)
        base_resolved = self.base_path.resolve()

        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            # Use only the filename to avoid double-nesting from legacy keys that
            # were stored as full relative paths (e.g. "storage/documents/uuid.pdf")
            resolved = (self.base_path / candidate.name).resolve()

        try:
            resolved.relative_to(base_resolved)
        except ValueError as exc:
            raise ValueError(f"storage_key fuera del directorio permitido: {storage_key}") from exc
        return resolved
