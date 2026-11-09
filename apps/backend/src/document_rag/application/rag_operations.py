"""Coordinate chunking, vector indexing, retrieval, and generation."""

import logging

from chromadb.api.models.Collection import Collection
from dynaconf.base import LazySettings
from openai import OpenAI
from sqlalchemy import Engine

from document_rag.application.document_operations import load_document_markdown
from document_rag.core.document_metadata import extract_document_metadata
from document_rag.infrastructure.chroma_store import (
    delete_document_chunks,
    query_document_chunks,
    replace_document_chunks,
)
from document_rag.infrastructure.chunking.hierarchical import (
    chunk_hierarchically,
)
from document_rag.infrastructure.chunking.semantic import (
    chunk_semantically,
    semantic_units_with_pages,
)
from document_rag.infrastructure.database import find_document, save_document
from document_rag.infrastructure.openai_client import (
    create_embeddings,
    generate_grounded_answer,
)

logger = logging.getLogger(__name__)


def build_answer_sources(
    retrieved_chunks: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Expand hierarchical context and preserve prompt citation ordering."""

    citation_sources = []
    used_context_ids = set()

    for chunk in retrieved_chunks:
        parent_text = str(chunk.get("parent_text") or "").strip()
        parent_id = str(chunk.get("parent_id") or "").strip()
        context_id = parent_id or str(chunk["id"])
        if context_id in used_context_ids:
            continue

        citation_source = dict(chunk)
        citation_source["text"] = parent_text or str(chunk["text"])
        parent_pages = str(chunk.get("parent_page_numbers") or "").strip()
        if parent_text and parent_pages:
            pages = [int(page) for page in parent_pages.split(",") if page]
            citation_source["page_numbers"] = parent_pages
            citation_source["page_start"] = min(pages)
            citation_source["page_end"] = max(pages)
        citation_sources.append(citation_source)
        used_context_ids.add(context_id)

    return citation_sources


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
    search_metadata = extract_document_metadata(document.original_name, markdown)
    document.status = "indexing"
    save_document(engine, document)

    try:
        if document.chunking_strategy is None:
            delete_document_chunks(collection, document_id)

        if strategy == "semantic":
            units, unit_page_numbers = semantic_units_with_pages(markdown)
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
                unit_page_numbers=unit_page_numbers,
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
            chunk["source_file"] = document.original_name
            chunk.update(search_metadata)
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
    strategy: str | None = None,
    *,
    retrieval_mode: str | None = None,
    top_k: int | None = None,
    document_hint_mode: str | None = None,
    strict_grounding: bool | None = None,
) -> dict[str, object]:
    """Retrieve document context, expand hierarchy, and generate an answer."""

    effective_retrieval_mode = retrieval_mode or getattr(
        settings,
        "RAG_RETRIEVAL_MODE",
        "embedding",
    )
    effective_top_k = top_k if top_k is not None else settings.RAG_TOP_K
    effective_hint_mode = document_hint_mode or getattr(
        settings,
        "RAG_DOCUMENT_HINT_MODE",
        "none",
    )
    effective_strict_grounding = (
        strict_grounding
        if strict_grounding is not None
        else bool(getattr(settings, "RAG_STRICT_GROUNDING", False))
    )

    query_embeddings = create_embeddings(
        openai_client,
        [question],
        settings.EMBEDDING_MODEL,
    )
    if effective_retrieval_mode == "embedding" and effective_hint_mode == "none":
        retrieved_chunks = query_document_chunks(
            collection,
            document_id,
            query_embeddings[0],
            effective_top_k,
            strategy,
        )
    else:
        retrieved_chunks = query_document_chunks(
            collection,
            document_id,
            query_embeddings[0],
            effective_top_k,
            strategy,
            query_text=question,
            retrieval_mode=effective_retrieval_mode,
            rrf_k=int(getattr(settings, "RAG_RRF_K", 60)),
            candidate_multiplier=int(
                getattr(settings, "RAG_HYBRID_CANDIDATE_MULTIPLIER", 4),
            ),
            document_hint_mode=effective_hint_mode,
        )
    if not retrieved_chunks:
        raise LookupError("No indexed context was found for this document")

    citation_sources = build_answer_sources(retrieved_chunks)

    if effective_strict_grounding:
        answer = generate_grounded_answer(
            openai_client,
            settings.GENERATION_MODEL,
            question,
            citation_sources,
            strict_grounding=True,
        )
    else:
        answer = generate_grounded_answer(
            openai_client,
            settings.GENERATION_MODEL,
            question,
            citation_sources,
        )

    return {
        "answer": answer,
        "sources": citation_sources,
        "model": settings.GENERATION_MODEL,
    }
