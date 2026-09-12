"""Tests for document storage and persistence behavior."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter

from document_rag.application.document_operations import (
    create_document,
    load_document_markdown,
    process_document,
    update_document_markdown,
)
from document_rag.core.models import DocumentRecord
from document_rag.infrastructure.database import (
    build_database,
    find_document,
    list_documents,
    save_document,
)
from document_rag.infrastructure.storage import (
    read_markdown,
    save_markdown,
    store_upload,
)


def test_database_persists_document_state(tmp_path: Path) -> None:
    """SQLite should preserve uploaded document state across transactions."""

    database_path = tmp_path / "state" / "documents.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = build_database(database_url)
    document = DocumentRecord(
        id="e407887d-6f96-43eb-8dd8-556078886a22",
        original_name="sample.md",
        stored_path=str(tmp_path / "uploads" / "sample.md"),
        media_type="text/markdown",
        size_bytes=42,
        status="uploaded",
    )

    saved_document = save_document(engine, document)
    saved_document.status = "ready"
    saved_document.markdown_path = str(tmp_path / "markdown" / "sample.md")
    save_document(engine, saved_document)

    loaded_document = find_document(engine, saved_document.id)
    documents = list_documents(engine)

    assert database_path.exists()
    assert loaded_document is not None
    assert loaded_document.status == "ready"
    assert loaded_document.markdown_path == saved_document.markdown_path
    assert [stored.id for stored in documents] == [saved_document.id]


def test_storage_round_trip_uses_safe_generated_paths(tmp_path: Path) -> None:
    """Uploads and edited Markdown should round-trip through local storage."""

    content = b"# Safety Notes\n\nWear eye protection.\n"
    upload_path, size_bytes = store_upload(
        "../unsafe report.MD",
        BytesIO(content),
        tmp_path / "uploads",
        max_bytes=1024,
    )
    markdown_path = save_markdown(
        "e407887d-6f96-43eb-8dd8-556078886a22",
        content.decode("utf-8"),
        tmp_path / "markdown",
    )

    assert upload_path.parent == (tmp_path / "uploads").resolve()
    assert upload_path.suffix == ".md"
    assert upload_path.name != "unsafe_report.md"
    assert size_bytes == len(content)
    assert read_markdown(markdown_path) == content.decode("utf-8")


def test_storage_removes_uploads_above_the_size_limit(tmp_path: Path) -> None:
    """An oversized upload should fail without leaving a partial file."""

    upload_directory = tmp_path / "uploads"

    with pytest.raises(ValueError, match="exceeds"):
        store_upload(
            "large.pdf",
            BytesIO(b"x" * 32),
            upload_directory,
            max_bytes=16,
        )

    assert list(upload_directory.iterdir()) == []


def test_document_workflow_extracts_and_accepts_edits(tmp_path: Path) -> None:
    """The document workflow should persist extraction output and user edits."""

    database_url = f"sqlite:///{(tmp_path / 'documents.db').as_posix()}"
    engine = build_database(database_url)
    sample_path = Path(__file__).parent / "samples" / "sample.md"

    with sample_path.open("rb") as sample_file:
        document = create_document(
            engine,
            file_name="sample.md",
            media_type="text/markdown",
            source=sample_file,
            upload_directory=tmp_path / "uploads",
            max_bytes=4096,
        )

    parsed_document = MagicMock()
    parsed_document.export_to_markdown.return_value = "# Extracted guide\n"
    conversion_result = SimpleNamespace(
        status=ConversionStatus.SUCCESS,
        document=parsed_document,
        errors=[],
    )
    converter = MagicMock(spec=DocumentConverter)
    converter.convert.return_value = conversion_result

    processed_document = process_document(
        engine,
        converter,
        document.id,
        markdown_directory=tmp_path / "markdown",
        max_file_size_bytes=4096,
        max_pages=20,
    )
    processed_document.chunking_strategy = "semantic"
    save_document(engine, processed_document)
    updated_document = update_document_markdown(
        engine,
        document.id,
        "# User revision\n",
        tmp_path / "markdown",
    )

    assert processed_document.status == "ready"
    assert load_document_markdown(engine, document.id) == "# User revision\n"
    assert updated_document.chunking_strategy is None
