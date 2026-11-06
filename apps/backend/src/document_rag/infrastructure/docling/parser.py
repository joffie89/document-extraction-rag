"""Convert supported local documents into editable Markdown."""

import logging
from pathlib import Path

from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling.exceptions import ConversionError

from document_rag.infrastructure.docling.formats import matching_formats

logger = logging.getLogger(__name__)

PAGE_MARKER_TEMPLATE = "<!-- docling-page: {page_number} -->"


def _export_markdown_with_page_markers(document: object) -> str:
    """Export Markdown with exact physical page markers when available."""

    pages = getattr(document, "pages", {})
    page_numbers = sorted(int(page_number) for page_number in pages)
    if not page_numbers:
        return document.export_to_markdown()

    sections = []
    for page_number in page_numbers:
        page_markdown = document.export_to_markdown(page_no=page_number).strip()
        section = PAGE_MARKER_TEMPLATE.format(page_number=page_number)
        if page_markdown:
            section = f"{section}\n\n{page_markdown}"
        sections.append(section)

    return "\n\n".join(sections)


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

    markdown = _export_markdown_with_page_markers(result.document)

    return markdown, result.status.value, errors
