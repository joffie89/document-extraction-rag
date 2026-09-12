"""Coordinate document uploads, extraction, and Markdown editing."""

import json
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from docling.document_converter import DocumentConverter
from sqlalchemy import Engine

from document_rag.core.models import DocumentRecord
from document_rag.infrastructure.database import (
    find_document,
    save_document,
)
from document_rag.infrastructure.docling.parser import extract_markdown
from document_rag.infrastructure.storage import (
    read_markdown,
    save_markdown,
    store_upload,
)

logger = logging.getLogger(__name__)


def create_document(
    engine: Engine,
    file_name: str,
    media_type: str | None,
    source: BinaryIO,
    upload_directory: str | Path,
    max_bytes: int,
) -> DocumentRecord:
    """Store an upload and persist its initial processing record."""

    stored_path, size_bytes = store_upload(
        file_name,
        source,
        upload_directory,
        max_bytes,
    )
    original_name = Path(file_name.replace("\\", "/")).name
    document = DocumentRecord(
        id=str(uuid4()),
        original_name=original_name,
        stored_path=str(stored_path),
        media_type=media_type,
        size_bytes=size_bytes,
        status="uploaded",
    )

    try:
        return save_document(engine, document)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise


def process_document(
    engine: Engine,
    converter: DocumentConverter,
    document_id: str,
    markdown_directory: str | Path,
    max_file_size_bytes: int,
    max_pages: int,
) -> DocumentRecord:
    """Extract an uploaded document and persist its Markdown result."""

    document = find_document(engine, document_id)
    if document is None:
        raise FileNotFoundError(f"Document {document_id} was not found")

    document.status = "extracting"
    save_document(engine, document)

    try:
        markdown, docling_status, warnings = extract_markdown(
            converter,
            document.stored_path,
            max_file_size_bytes,
            max_pages,
        )
        markdown_path = save_markdown(
            document.id,
            markdown,
            markdown_directory,
        )
    except Exception as exc:
        document.status = "failed"
        document.extraction_message = str(exc)
        save_document(engine, document)
        logger.exception("Extraction failed for document %s", document.id)
        raise

    document.status = "ready"
    document.markdown_path = str(markdown_path)
    document.extraction_message = json.dumps(
        {
            "docling_status": docling_status,
            "warnings": warnings,
        },
    )

    return save_document(engine, document)


def update_document_markdown(
    engine: Engine,
    document_id: str,
    markdown: str,
    markdown_directory: str | Path,
) -> DocumentRecord:
    """Save a user's Markdown edit and invalidate its previous chunks."""

    document = find_document(engine, document_id)
    if document is None:
        raise FileNotFoundError(f"Document {document_id} was not found")

    markdown_path = save_markdown(document.id, markdown, markdown_directory)
    document.markdown_path = str(markdown_path)
    document.status = "ready"
    document.chunking_strategy = None

    return save_document(engine, document)


def load_document_markdown(engine: Engine, document_id: str) -> str:
    """Load editable Markdown for a successfully extracted document."""

    document = find_document(engine, document_id)
    if document is None:
        raise FileNotFoundError(f"Document {document_id} was not found")
    if document.markdown_path is None:
        raise FileNotFoundError(f"Document {document_id} has no Markdown output")

    return read_markdown(document.markdown_path)
