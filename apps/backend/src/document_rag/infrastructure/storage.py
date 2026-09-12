"""Safe local storage for uploads and editable Markdown."""

import re
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4


def store_upload(
    file_name: str,
    source: BinaryIO,
    upload_directory: str | Path,
    max_bytes: int,
) -> tuple[Path, int]:
    """Stream an upload to disk while enforcing its configured size limit."""

    original_name = Path(file_name.replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original_name).strip("._")
    if not safe_name:
        raise ValueError("The uploaded file name is invalid")

    destination_directory = Path(upload_directory).expanduser().resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)
    suffix = "".join(Path(safe_name).suffixes).lower()
    destination = destination_directory / f"{uuid4().hex}{suffix}"
    total_bytes = 0

    try:
        with destination.open("xb") as stored_file:
            while chunk := source.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise ValueError(f"Upload exceeds the {max_bytes}-byte limit")
                stored_file.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return destination, total_bytes


def save_markdown(
    document_id: str,
    markdown: str,
    markdown_directory: str | Path,
) -> Path:
    """Atomically save the latest Markdown for a document."""

    normalized_id = str(UUID(document_id))
    destination_directory = Path(markdown_directory).expanduser().resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{normalized_id}.md"
    temporary_path = destination_directory / f".{normalized_id}.tmp"

    temporary_path.write_text(markdown, encoding="utf-8")
    temporary_path.replace(destination)

    return destination


def read_markdown(markdown_path: str | Path) -> str:
    """Read a document's current Markdown from its stored path."""

    source_path = Path(markdown_path).expanduser().resolve(strict=True)
    if not source_path.is_file():
        raise IsADirectoryError(source_path)

    return source_path.read_text(encoding="utf-8")
