"""Convert supported local documents into editable Markdown."""

import logging
from pathlib import Path

from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling.exceptions import ConversionError

from document_rag.infrastructure.docling.formats import matching_formats

logger = logging.getLogger(__name__)


def extract_markdown(
    converter: DocumentConverter,
    source: str | Path,
    max_file_size_bytes: int,
    max_pages: int,
) -> tuple[str, str, list[dict[str, object]]]:
    """Convert one supported file and retain Docling warning details."""

    source_path = Path(source).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise IsADirectoryError(source_path)
    if not matching_formats(source_path.name):
        raise ValueError(f"Docling does not support {source_path.name}")

    try:
        result = converter.convert(
            source=source_path,
            raises_on_error=False,
            max_file_size=max_file_size_bytes,
            max_num_pages=max_pages,
        )
    except (ConversionError, StopIteration) as exc:
        logger.exception("Docling could not convert %s", source_path.name)
        message = f"Document extraction failed for {source_path.name}"
        raise RuntimeError(message) from exc

    errors = [error.model_dump(mode="json") for error in result.errors]
    accepted_statuses = {
        ConversionStatus.SUCCESS,
        ConversionStatus.PARTIAL_SUCCESS,
    }

    if result.status not in accepted_statuses:
        logger.error(
            "Docling returned %s for %s",
            result.status.value,
            source_path.name,
        )
        raise RuntimeError(
            f"Document extraction ended with status {result.status.value}",
        )

    markdown = result.document.export_to_markdown()

    return markdown, result.status.value, errors
