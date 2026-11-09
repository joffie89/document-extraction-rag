"""Upload every PDF in a corpus and prepare both supported RAG strategies."""

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_DIRECTORY = PROJECT_ROOT / "data" / "corpus"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
STRATEGIES = ("semantic", "hierarchical")
INGESTION_ERRORS = (OSError, ValueError, RuntimeError, requests.RequestException)


def discover_pdfs(corpus_directory: str | Path) -> list[Path]:
    """Return every PDF below a corpus directory in deterministic order."""

    root = Path(corpus_directory).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Corpus directory does not exist: {root}")

    pdfs = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() == ".pdf"
    ]
    return sorted(pdfs, key=lambda path: path.relative_to(root).as_posix().casefold())


def _response_json(response: requests.Response) -> dict[str, Any]:
    """Validate an HTTP response and return its JSON object."""

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("The RAG API returned a non-object JSON response")
    return payload


def _sha256(path: Path) -> str:
    """Return a stable fingerprint for one corpus file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _completed_documents(
    manifest_path: Path,
    base_url: str,
) -> dict[str, dict[str, Any]]:
    """Load successful entries that can be reused on a resumed run."""

    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read ingestion manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("base_url") != base_url:
        return {}

    completed = {}
    for document in manifest.get("documents", []):
        if not isinstance(document, dict) or document.get("error"):
            continue
        strategies = document.get("strategies")
        if not isinstance(strategies, dict):
            continue
        if not all(
            isinstance(strategies.get(strategy), dict)
            and strategies[strategy].get("status") == "indexed"
            for strategy in STRATEGIES
        ):
            continue
        source_file = str(document.get("source_file") or "")
        if source_file and document.get("document_id") and document.get("sha256"):
            completed[source_file] = document
    return completed


def _wait_until_ready(
    session: requests.Session,
    base_url: str,
    document_id: str,
    processing_timeout: float,
    poll_interval: float,
    request_timeout: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> None:
    """Poll one uploaded document until extraction completes."""

    deadline = monotonic() + processing_timeout
    while True:
        document = _response_json(
            session.get(
                f"{base_url}/documents/{document_id}",
                timeout=request_timeout,
            ),
        )
        status = str(document.get("status") or "")
        if status in {"ready", "indexed"}:
            return
        if status == "failed":
            raise RuntimeError(f"Extraction failed for document {document_id}")
        if monotonic() >= deadline:
            raise TimeoutError(f"Extraction timed out for document {document_id}")
        sleep(poll_interval)


def ingest_corpus(
    corpus_directory: str | Path = DEFAULT_CORPUS_DIRECTORY,
    *,
    base_url: str = DEFAULT_BASE_URL,
    manifest_path: str | Path | None = None,
    processing_timeout: float = 900,
    poll_interval: float = 1,
    request_timeout: float = 600,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    force: bool = False,
) -> dict[str, object]:
    """Upload each changed PDF, prepare both indexes, and write their query IDs."""

    corpus_root = Path(corpus_directory).expanduser().resolve()
    pdfs = discover_pdfs(corpus_root)
    if not pdfs:
        raise ValueError(f"No PDF files were found in {corpus_root}")
    if processing_timeout <= 0 or poll_interval < 0 or request_timeout <= 0:
        raise ValueError(
            "Timeouts must be positive and poll interval cannot be negative",
        )

    api_root = base_url.rstrip("/")
    output_path = (
        Path(manifest_path).expanduser().resolve()
        if manifest_path is not None
        else corpus_root / "ingestion_manifest.json"
    )
    completed = {} if force else _completed_documents(output_path, api_root)
    active_session = session or requests.Session()
    owns_session = session is None
    documents = []

    try:
        for pdf_path in pdfs:
            source_file = pdf_path.relative_to(corpus_root).as_posix()
            document: dict[str, Any] = {
                "source_file": source_file,
                "sha256": "",
                "document_id": "",
                "strategies": {},
            }
            try:
                fingerprint = _sha256(pdf_path)
                document["sha256"] = fingerprint
                previous = completed.get(source_file)
                if previous is not None and previous.get("sha256") == fingerprint:
                    documents.append(previous)
                    continue

                with pdf_path.open("rb") as pdf_file:
                    uploaded = _response_json(
                        active_session.post(
                            f"{api_root}/documents",
                            files={
                                "file": (pdf_path.name, pdf_file, "application/pdf"),
                            },
                            timeout=request_timeout,
                        ),
                    )
                document_id = str(uploaded.get("id") or "")
                if not document_id:
                    raise RuntimeError("The RAG API did not return a document ID")
                document["document_id"] = document_id

                _wait_until_ready(
                    active_session,
                    api_root,
                    document_id,
                    processing_timeout,
                    poll_interval,
                    request_timeout,
                    sleep,
                    monotonic,
                )

                prepared_strategies = document["strategies"]
                for strategy in STRATEGIES:
                    prepared = _response_json(
                        active_session.post(
                            f"{api_root}/documents/{document_id}/rag",
                            json={"strategy": strategy},
                            timeout=request_timeout,
                        ),
                    )
                    prepared_strategies[strategy] = {
                        "chunk_count": int(prepared.get("chunk_count") or 0),
                        "status": str(prepared.get("status") or ""),
                    }
            except INGESTION_ERRORS as exc:
                document["error"] = str(exc)
            documents.append(document)
    finally:
        if owns_session:
            active_session.close()

    manifest: dict[str, object] = {
        "corpus_directory": str(corpus_root),
        "base_url": api_root,
        "documents": documents,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the domain-neutral corpus ingestion CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIRECTORY,
        help="PDF directory to ingest (default: data/corpus)",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Output manifest (default: <corpus-dir>/ingestion_manifest.json)",
    )
    parser.add_argument("--processing-timeout", type=float, default=900)
    parser.add_argument("--poll-interval", type=float, default=1)
    parser.add_argument("--request-timeout", type=float, default=600)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload PDFs even when their manifest fingerprints match",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run corpus ingestion from command-line arguments."""

    arguments = build_argument_parser().parse_args(argv)
    try:
        manifest = ingest_corpus(
            arguments.corpus_dir,
            base_url=arguments.base_url,
            manifest_path=arguments.manifest,
            processing_timeout=arguments.processing_timeout,
            poll_interval=arguments.poll_interval,
            request_timeout=arguments.request_timeout,
            force=arguments.force,
        )
    except INGESTION_ERRORS as exc:
        print(f"Corpus ingestion failed: {exc}", file=sys.stderr)
        return 1

    failed = False
    for document in manifest["documents"]:
        if document.get("error"):
            failed = True
            print(
                f"{document['source_file']}: ERROR: {document['error']}",
                file=sys.stderr,
            )
        else:
            print(
                f"{document['source_file']}: {document['document_id']} "
                f"({', '.join(STRATEGIES)})",
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
