"""Coordinate chunking, vector indexing, retrieval, and generation."""

import logging

from chromadb.api.models.Collection import Collection
from dynaconf.base import LazySettings
from openai import OpenAI
from sqlalchemy import Engine

from document_rag.application.document_operations import load_document_markdown
from document_rag.infrastructure.chroma_store import (
    query_document_chunks,
    replace_document_chunks,
)
from document_rag.infrastructure.chunking.hierarchical import (
    chunk_hierarchically,
)
from document_rag.infrastructure.chunking.semantic import (
    chunk_semantically,
    semantic_units,
)
from document_rag.infrastructure.database import find_document, save_document
from document_rag.infrastructure.openai_client import (
    create_embeddings,
    generate_grounded_answer,
)

logger = logging.getLogger(__name__)


def prepare_document_for_rag(
    engine: Engine,
    collection: Collection,
    openai_client: OpenAI,
    document_id: str,
    strategy: str,
    settings: LazySettings,
) -> list[dict[str, object]]:
    """Chunk current Markdown, embed retrieval units, and replace its index."""

    if strategy not in {"semantic", "hierarchical"}:
        raise ValueError("Chunking strategy must be semantic or hierarchical")

    document = find_document(engine, document_id)
    if document is None:
        raise FileNotFoundError(f"Document {document_id} was not found")

    markdown = load_document_markdown(engine, document_id)
    document.status = "indexing"
    save_document(engine, document)

    try:
        if strategy == "semantic":
            units = semantic_units(markdown)
            unit_embeddings = create_embeddings(
                openai_client,
                units,
                settings.EMBEDDING_MODEL,
            )
            chunks = chunk_semantically(
                units,
                unit_embeddings,
                settings.SEMANTIC_BREAK_PERCENTILE,
                settings.MIN_CHUNK_TOKENS,
                settings.MAX_CHUNK_TOKENS,
            )
        else:
            hierarchy = chunk_hierarchically(
                markdown,
                document_id,
                settings.MAX_CHUNK_TOKENS,
            )
            chunks = []
            for node in hierarchy:
                if node["kind"] == "paragraph":
                    chunks.append(node)

        if not chunks:
            raise ValueError("The Markdown did not produce any indexable chunks")

        chunk_texts = []
        for chunk in chunks:
            chunk_texts.append(str(chunk["text"]))

        chunk_embeddings = create_embeddings(
            openai_client,
            chunk_texts,
            settings.EMBEDDING_MODEL,
        )
        replace_document_chunks(
            collection,
            document_id,
            strategy,
            chunks,
            chunk_embeddings,
        )
    except Exception:
        document.status = "ready"
        save_document(engine, document)
        logger.exception("RAG preparation failed for document %s", document_id)
        raise

    document.status = "indexed"
    document.chunking_strategy = strategy
    save_document(engine, document)

    return chunks


def answer_document_question(
    collection: Collection,
    openai_client: OpenAI,
    document_id: str,
    question: str,
    settings: LazySettings,
) -> dict[str, object]:
    """Retrieve document context, expand hierarchy, and generate an answer."""

    query_embeddings = create_embeddings(
        openai_client,
        [question],
        settings.EMBEDDING_MODEL,
    )
    retrieved_chunks = query_document_chunks(
        collection,
        document_id,
        query_embeddings[0],
        settings.RAG_TOP_K,
    )
    if not retrieved_chunks:
        raise LookupError("No indexed context was found for this document")

    context_chunks = []
    used_context_ids = set()

    for chunk in retrieved_chunks:
        parent_text = str(chunk.get("parent_text") or "").strip()
        parent_id = str(chunk.get("parent_id") or "").strip()
        context_id = parent_id or str(chunk["id"])
        if context_id in used_context_ids:
            continue

        context_chunks.append(
            {
                "text": parent_text or str(chunk["text"]),
                "heading_path": chunk.get("heading_path", ""),
            },
        )
        used_context_ids.add(context_id)

    answer = generate_grounded_answer(
        openai_client,
        settings.GENERATION_MODEL,
        question,
        context_chunks,
    )

    return {
        "answer": answer,
        "sources": retrieved_chunks,
        "model": settings.GENERATION_MODEL,
    }
