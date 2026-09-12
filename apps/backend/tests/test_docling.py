"""Tests for Docling format handling and Markdown extraction."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.document_converter import DocumentConverter

from document_rag.infrastructure.docling.configuration import (
    build_document_converter,
)
from document_rag.infrastructure.docling.formats import (
    matching_formats,
    supported_formats,
)
from document_rag.infrastructure.docling.parser import extract_markdown


def test_document_converter_enables_registered_formats() -> None:
    """The converter should accept every format registered by Docling."""

    converter = build_document_converter(timeout_seconds=30)

    assert set(converter.allowed_formats) == set(InputFormat)


def test_document_converter_rejects_non_english_ocr() -> None:
    """The extraction configuration should enforce English-only OCR."""

    with pytest.raises(ValueError, match="English"):
        build_document_converter(timeout_seconds=30, ocr_language="fr")


def test_format_matching_handles_ambiguous_and_compound_extensions() -> None:
    """Format matching should keep ambiguity and prefer compound extensions."""

    formats = supported_formats()
    xml_matches = matching_formats("filing.xml")

    assert formats[InputFormat.PDF.value] == (".pdf",)
    assert InputFormat.XML_JATS.value in xml_matches
    assert InputFormat.XML_XBRL.value in xml_matches
    assert matching_formats("export.dclg.xml") == [InputFormat.XML_DOCLANG.value]
    assert matching_formats("archive.tar.gz") == [InputFormat.METS_GBS.value]
    assert matching_formats("unknown.binary") == []


def test_parser_returns_markdown_and_partial_warnings() -> None:
    """The parser should preserve Markdown and warnings from usable results."""

    sample_path = Path(__file__).parent / "samples" / "sample.md"
    parsed_document = MagicMock()
    parsed_document.export_to_markdown.return_value = "# Extracted\n"
    warning = MagicMock()
    warning.model_dump.return_value = {"message": "One image was skipped"}
    conversion_result = SimpleNamespace(
        status=ConversionStatus.PARTIAL_SUCCESS,
        document=parsed_document,
        errors=[warning],
    )
    converter = MagicMock(spec=DocumentConverter)
    converter.convert.return_value = conversion_result

    markdown, status, warnings = extract_markdown(
        converter,
        sample_path,
        max_file_size_bytes=1024,
        max_pages=10,
    )

    assert markdown == "# Extracted\n"
    assert status == ConversionStatus.PARTIAL_SUCCESS.value
    assert warnings == [{"message": "One image was skipped"}]
    converter.convert.assert_called_once_with(
        source=sample_path.resolve(),
        raises_on_error=False,
        max_file_size=1024,
        max_num_pages=10,
    )


def test_parser_rejects_failed_conversion() -> None:
    """A failed Docling result should become a clear runtime error."""

    sample_path = Path(__file__).parent / "samples" / "sample.csv"
    conversion_result = SimpleNamespace(
        status=ConversionStatus.FAILURE,
        document=MagicMock(),
        errors=[],
    )
    converter = MagicMock(spec=DocumentConverter)
    converter.convert.return_value = conversion_result

    with pytest.raises(RuntimeError, match="status failure"):
        extract_markdown(
            converter,
            sample_path,
            max_file_size_bytes=1024,
            max_pages=10,
        )
