"""Tests for domain-neutral batch corpus ingestion."""

import json
from pathlib import Path

import ingest_corpus


class FakeResponse:
    """Return one successful JSON response without network access."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        """Mirror a successful requests response."""

    def json(self) -> dict[str, object]:
        """Return the configured response body."""

        return self.payload


class FakeSession:
    """Record uploads, polls, and preparation requests."""

    def __init__(self) -> None:
        self.uploaded_files: list[str] = []
        self.preparations: list[tuple[str, str]] = []
        self.document_ids: list[str] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        """Simulate document upload or RAG preparation."""

        if url.endswith("/documents"):
            files = kwargs["files"]
            file_name = files["file"][0]
            document_id = f"document-{len(self.document_ids) + 1}"
            self.uploaded_files.append(file_name)
            self.document_ids.append(document_id)
            return FakeResponse({"id": document_id, "status": "uploaded"})

        document_id = url.split("/")[-2]
        strategy = kwargs["json"]["strategy"]
        self.preparations.append((document_id, strategy))
        return FakeResponse(
            {
                "document_id": document_id,
                "strategy": strategy,
                "chunk_count": 3,
                "status": "indexed",
            },
        )

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        """Report extraction as ready on the first poll."""

        return FakeResponse({"id": url.rsplit("/", 1)[-1], "status": "ready"})


class FailingSession(FakeSession):
    """Fail one upload while allowing later corpus files to continue."""

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        """Reject B.PDF and delegate every other request."""

        if url.endswith("/documents"):
            file_name = kwargs["files"]["file"][0]
            if file_name == "B.PDF":
                raise RuntimeError("fixture upload failed")
        return super().post(url, **kwargs)


def test_ingest_corpus_discovers_every_pdf_and_prepares_both_strategies(
    tmp_path: Path,
) -> None:
    """Every PDF should be uploaded once and retain two queryable indexes."""

    corpus_directory = tmp_path / "corpus"
    nested_directory = corpus_directory / "nested"
    nested_directory.mkdir(parents=True)
    (nested_directory / "a.pdf").write_bytes(b"%PDF-1.4 fixture a")
    (corpus_directory / "B.PDF").write_bytes(b"%PDF-1.4 fixture b")
    (corpus_directory / "notes.txt").write_text("ignore me", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    session = FakeSession()

    manifest = ingest_corpus.ingest_corpus(
        corpus_directory,
        base_url="http://rag.test/api/v1/",
        manifest_path=manifest_path,
        session=session,
    )

    assert ingest_corpus.DEFAULT_CORPUS_DIRECTORY == (
        Path(ingest_corpus.__file__).resolve().parent / "data" / "corpus"
    )
    assert session.uploaded_files == ["B.PDF", "a.pdf"]
    assert session.preparations == [
        ("document-1", "semantic"),
        ("document-1", "hierarchical"),
        ("document-2", "semantic"),
        ("document-2", "hierarchical"),
    ]
    documents = manifest["documents"]
    assert len(documents) == 2
    assert all(
        set(document["strategies"]) == {"semantic", "hierarchical"}
        for document in documents
    )
    assert all(len(document["sha256"]) == 64 for document in documents)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest

    resumed_manifest = ingest_corpus.ingest_corpus(
        corpus_directory,
        base_url="http://rag.test/api/v1/",
        manifest_path=manifest_path,
        session=session,
    )

    assert resumed_manifest == manifest
    assert session.uploaded_files == ["B.PDF", "a.pdf"]
    assert len(session.preparations) == 4


def test_ingest_corpus_records_failure_and_continues_with_later_pdfs(
    tmp_path: Path,
) -> None:
    """One failed PDF should not prevent the remaining corpus from indexing."""

    corpus_directory = tmp_path / "corpus"
    nested_directory = corpus_directory / "nested"
    nested_directory.mkdir(parents=True)
    (corpus_directory / "B.PDF").write_bytes(b"%PDF-1.4 broken fixture")
    (nested_directory / "a.pdf").write_bytes(b"%PDF-1.4 valid fixture")
    session = FailingSession()

    manifest = ingest_corpus.ingest_corpus(
        corpus_directory,
        base_url="http://rag.test/api/v1",
        manifest_path=tmp_path / "manifest.json",
        session=session,
    )

    failed_document, indexed_document = manifest["documents"]
    assert failed_document["source_file"] == "B.PDF"
    assert failed_document["error"] == "fixture upload failed"
    assert indexed_document["source_file"] == "nested/a.pdf"
    assert set(indexed_document["strategies"]) == {"semantic", "hierarchical"}


def test_ingest_corpus_records_hash_failure_and_continues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """An unreadable PDF should not prevent later corpus files from indexing."""

    corpus_directory = tmp_path / "corpus"
    corpus_directory.mkdir()
    bad_pdf = corpus_directory / "a.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4 unreadable fixture")
    (corpus_directory / "b.pdf").write_bytes(b"%PDF-1.4 valid fixture")
    real_sha256 = ingest_corpus._sha256

    def fail_first_hash(path: Path) -> str:
        if path == bad_pdf:
            raise OSError("fixture read failed")
        return real_sha256(path)

    monkeypatch.setattr(ingest_corpus, "_sha256", fail_first_hash)
    session = FakeSession()

    manifest = ingest_corpus.ingest_corpus(
        corpus_directory,
        base_url="http://rag.test/api/v1",
        manifest_path=tmp_path / "manifest.json",
        session=session,
    )

    failed_document, indexed_document = manifest["documents"]
    assert failed_document["source_file"] == "a.pdf"
    assert failed_document["error"] == "fixture read failed"
    assert indexed_document["source_file"] == "b.pdf"
    assert set(indexed_document["strategies"]) == {"semantic", "hierarchical"}
