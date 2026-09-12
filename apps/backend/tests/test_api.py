"""Tests for configuration and the HTTP boundary."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from dynaconf.validator import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient

import document_rag.api.routes as routes_module
from document_rag.api.routes import router
from document_rag.core.config import load_settings
from document_rag.core.models import DocumentRecord
from document_rag.infrastructure.database import build_database, save_document
from document_rag.infrastructure.storage import save_markdown

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"


def test_load_settings_reads_valid_dotenv_values(tmp_path: Path) -> None:
    """Dynaconf should load valid application values from a dotenv file."""

    env_file = tmp_path / ".env"
    environment = ENV_EXAMPLE.read_text(encoding="utf-8")
    environment = environment.replace("ENVIRONMENT=production", "ENVIRONMENT=test")
    environment = environment.replace(
        "MAX_CHUNK_TOKENS=800",
        "MAX_CHUNK_TOKENS=640",
    )
    env_file.write_text(
        environment,
        encoding="utf-8",
    )

    application_settings = load_settings(env_file)

    assert application_settings.ENVIRONMENT == "test"
    assert application_settings.MAX_CHUNK_TOKENS == 640
    assert application_settings.OCR_LANGUAGE == "en"


def test_load_settings_rejects_invalid_token_range(tmp_path: Path) -> None:
    """Configuration should reject a minimum larger than its maximum."""

    env_file = tmp_path / ".env"
    environment = ENV_EXAMPLE.read_text(encoding="utf-8")
    environment = environment.replace("MIN_CHUNK_TOKENS=100", "MIN_CHUNK_TOKENS=900")
    env_file.write_text(
        environment,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="MIN_CHUNK_TOKENS"):
        load_settings(env_file)


def test_load_settings_requires_openai_key_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI configuration should be mandatory only for AI operations."""

    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("MIN_CHUNK_TOKENS", raising=False)
    monkeypatch.delenv("MAX_CHUNK_TOKENS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        ENV_EXAMPLE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_settings(env_file, require_openai=True)


def test_api_supports_document_editing_and_rag_requests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTP boundary should expose the complete local document workflow."""

    engine = build_database(
        f"sqlite:///{(tmp_path / 'documents.db').as_posix()}",
    )
    document_id = "b1cfdbe8-859d-4481-9133-d2f4c0aac9ae"
    markdown_path = save_markdown(
        document_id,
        "# Safety\n\nWear safety glasses.\n",
        tmp_path / "markdown",
    )
    document = DocumentRecord(
        id=document_id,
        original_name="safety.md",
        stored_path=str(markdown_path),
        markdown_path=str(markdown_path),
        media_type="text/markdown",
        size_bytes=markdown_path.stat().st_size,
        status="ready",
    )
    save_document(engine, document)

    application = FastAPI()
    application.state.engine = engine
    application.state.converter = MagicMock()
    application.state.collection = MagicMock()
    application.state.openai_client = MagicMock()
    application.state.settings = SimpleNamespace(
        UPLOAD_DIRECTORY=str(tmp_path / "uploads"),
        MARKDOWN_DIRECTORY=str(tmp_path / "markdown"),
        MAX_UPLOAD_BYTES=4096,
        MAX_DOCUMENT_PAGES=20,
    )
    application.include_router(router, prefix="/api/v1")

    process_mock = MagicMock()
    prepare_mock = MagicMock(
        return_value=[{"text": "First chunk"}, {"text": "Second chunk"}],
    )
    answer_mock = MagicMock(
        return_value={
            "answer": "Wear safety glasses [Source 1].",
            "model": "gpt-4.1-mini",
            "sources": [
                {
                    "id": "source-1",
                    "text": "Wear safety glasses.",
                    "distance": 0.02,
                },
            ],
        },
    )
    monkeypatch.setattr(routes_module, "process_document", process_mock)
    monkeypatch.setattr(routes_module, "prepare_document_for_rag", prepare_mock)
    monkeypatch.setattr(routes_module, "answer_document_question", answer_mock)

    with TestClient(application) as client:
        health_response = client.get("/api/v1/health")
        formats_response = client.get("/api/v1/formats")
        documents_response = client.get("/api/v1/documents")
        markdown_response = client.get(
            f"/api/v1/documents/{document_id}/markdown",
        )
        edit_response = client.put(
            f"/api/v1/documents/{document_id}/markdown",
            json={"markdown": "# Revised safety\n"},
        )
        rag_response = client.post(
            f"/api/v1/documents/{document_id}/rag",
            json={"strategy": "hierarchical"},
        )
        answer_response = client.post(
            f"/api/v1/documents/{document_id}/ask",
            json={"question": "What protects the eyes?"},
        )
        upload_response = client.post(
            "/api/v1/documents",
            files={"file": ("new.md", b"# New document\n", "text/markdown")},
        )

    assert health_response.json() == {"status": "healthy"}
    assert ".pdf" in formats_response.json()["pdf"]
    assert documents_response.json()[0]["id"] == document_id
    assert markdown_response.json()["markdown"].startswith("# Safety")
    assert edit_response.json()["status"] == "ready"
    assert rag_response.json()["chunk_count"] == 2
    assert rag_response.json()["strategy"] == "hierarchical"
    assert answer_response.json()["model"] == "gpt-4.1-mini"
    assert upload_response.status_code == 202
    process_mock.assert_called_once()
