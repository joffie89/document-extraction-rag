"""Persist and query OpenAI vectors with local ChromaDB."""

from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings


def _page_numbers(value: object) -> list[int]:
    """Normalize chunk page metadata for scalar Chroma storage."""

    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = []

    return sorted({int(page) for page in candidates if str(page).strip()})


def prepare_collection(
    chroma_directory: str | Path,
    collection_name: str,
) -> Collection:
    """Open a persistent cosine-distance collection without an embedder."""

    if len(collection_name.strip()) < 3:
        raise ValueError("The Chroma collection name must have at least 3 characters")

    storage_path = Path(chroma_directory).expanduser().resolve()
    storage_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(storage_path),
        settings=Settings(anonymized_telemetry=False),
    )

    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}},
    )


def delete_document_chunks(
    collection: Collection,
    document_id: str,
) -> None:
    """Delete every stored strategy for one document."""

    collection.delete(where={"document_id": document_id})


def replace_document_chunks(
    collection: Collection,
    document_id: str,
    strategy: str,
    chunks: list[dict[str, object]],
    embeddings: list[list[float]],
) -> int:
    """Replace one document strategy's vectors with a complete chunk set."""

    if strategy not in {"semantic", "hierarchical"}:
        raise ValueError("Chunking strategy must be semantic or hierarchical")
    if len(chunks) != len(embeddings):
        raise ValueError("Each indexed chunk requires one embedding")

    strategy_filter = {
        "$and": [
            {"document_id": document_id},
            {"strategy": strategy},
        ],
    }
    collection.delete(where=strategy_filter)
    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        text = str(chunk.get("text") or "").strip()
        if not text:
            raise ValueError("Indexed chunks cannot be blank")

        chunk_id = str(chunk.get("id") or f"{document_id}:{strategy}:{index}")
        parent_id = str(chunk.get("parent_id") or "")
        metadata: dict[str, str | int] = {
            "document_id": document_id,
            "strategy": strategy,
            "ordinal": int(chunk.get("ordinal", index)),
            "kind": str(chunk.get("kind") or strategy),
            "level": int(chunk.get("level", 0)),
            "heading_path": str(chunk.get("heading_path") or ""),
            "parent_id": parent_id,
        }
        parent_text = str(chunk.get("parent_text") or "").strip()
        if parent_text:
            metadata["parent_text"] = parent_text
        source_file = str(chunk.get("source_file") or "").strip()
        if source_file:
            metadata["source_file"] = source_file
        pages = _page_numbers(chunk.get("page_numbers"))
        if pages:
            metadata["page_numbers"] = ",".join(str(page) for page in pages)
            metadata["page_start"] = pages[0]
            metadata["page_end"] = pages[-1]
        parent_pages = _page_numbers(chunk.get("parent_page_numbers"))
        if parent_pages:
            metadata["parent_page_numbers"] = ",".join(
                str(page) for page in parent_pages
            )

        ids.append(chunk_id)
        documents.append(text)
        metadatas.append(metadata)

    if len(ids) != len(set(ids)):
        raise ValueError("Chunk identifiers must be unique")

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


def query_document_chunks(
    collection: Collection,
    document_id: str,
    query_embedding: list[float],
    result_count: int,
    strategy: str | None = None,
) -> list[dict[str, object]]:
    """Retrieve the closest chunks for one indexed document."""

    if strategy is not None and strategy not in {"semantic", "hierarchical"}:
        raise ValueError("Chunking strategy must be semantic or hierarchical")

    where: dict[str, object] = {"document_id": document_id}
    if strategy is not None:
        where = {
            "$and": [
                {"document_id": document_id},
                {"strategy": strategy},
            ],
        }

    return _query_chunks(collection, query_embedding, result_count, where=where)


def query_collection_chunks(
    collection: Collection,
    query_embedding: list[float],
    result_count: int,
) -> list[dict[str, object]]:
    """Retrieve the closest chunks across an entire collection."""

    return _query_chunks(collection, query_embedding, result_count)


def _query_chunks(
    collection: Collection,
    query_embedding: list[float],
    result_count: int,
    *,
    where: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """Run one validated nearest-neighbour query with an optional filter."""

    if not query_embedding:
        raise ValueError("A query embedding is required")
    if result_count < 1:
        raise ValueError("The result count must be positive")

    collection_size = collection.count()
    if collection_size == 0:
        return []

    query_arguments: dict[str, object] = {
        "query_embeddings": [query_embedding],
        "n_results": min(result_count, collection_size),
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        query_arguments["where"] = where

    results = collection.query(
        **query_arguments,
    )
    ids = results.get("ids") or [[]]
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    retrieved_chunks = []

    for index, text in enumerate(documents[0]):
        metadata = dict(metadatas[0][index] or {})
        metadata["id"] = ids[0][index]
        metadata["text"] = text
        metadata["distance"] = float(distances[0][index])
        retrieved_chunks.append(metadata)

    return retrieved_chunks
