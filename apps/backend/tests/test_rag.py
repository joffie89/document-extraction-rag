"""Tests for vector indexing, retrieval, and grounded generation."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from document_rag.application.rag_operations import (
    answer_document_question,
    prepare_document_for_rag,
)
from document_rag.core.models import DocumentRecord
from document_rag.infrastructure.chroma_store import (
    prepare_collection,
    query_document_chunks,
    replace_document_chunks,
)
from document_rag.infrastructure.chunking.semantic import (
    chunk_semantically,
    semantic_units,
)
from document_rag.infrastructure.database import (
    build_database,
    find_document,
    save_document,
)
from document_rag.infrastructure.openai_client import (
    create_embeddings,
    generate_grounded_answer,
)


def test_create_embeddings_restores_input_order() -> None:
    """Embedding output should align with the original text sequence."""

    client = MagicMock()
    client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ],
    )

    embeddings = create_embeddings(
        client,
        ["First block", "Second block"],
        model="text-embedding-3-small",
    )

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["First block", "Second block"],
        encoding_format="float",
    )


def test_generate_grounded_answer_supplies_numbered_sources() -> None:
    """Generation should receive source labels and return response text."""

    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="Wear safety glasses [Source 1].",
    )
    chunks = [
        {
            "text": "Wear safety glasses whenever machinery is operating.",
            "heading_path": "Safety > Equipment",
        },
    ]

    answer = generate_grounded_answer(
        client,
        model="gpt-4.1-mini",
        question="What eye protection is required?",
        retrieved_chunks=chunks,
    )

    request = client.responses.create.call_args.kwargs
    assert answer == "Wear safety glasses [Source 1]."
    assert request["model"] == "gpt-4.1-mini"
    assert "[Source 1] Safety > Equipment" in request["input"]
    assert request["store"] is False


def test_chroma_replaces_and_queries_document_chunks(tmp_path: Path) -> None:
    """Chroma should replace stale vectors and return the nearest chunk."""

    collection = prepare_collection(tmp_path / "chroma", "test_chunks")
    chunks = [
        {
            "text": "Safety glasses protect the eyes.",
            "ordinal": 0,
            "kind": "semantic",
            "level": 0,
            "heading_path": "Safety > Equipment",
        },
        {
            "text": "Evacuate when the alarm sounds.",
            "ordinal": 1,
            "kind": "semantic",
            "level": 0,
            "heading_path": "Safety > Emergencies",
        },
    ]

    indexed_count = replace_document_chunks(
        collection,
        document_id="safety-guide",
        strategy="semantic",
        chunks=chunks,
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
    )
    results = query_document_chunks(
        collection,
        document_id="safety-guide",
        query_embedding=[0.99, 0.01],
        result_count=2,
    )
    replacement_count = replace_document_chunks(
        collection,
        document_id="safety-guide",
        strategy="hierarchical",
        chunks=[
            {
                "id": "safety-guide:replacement",
                "text": "Use replacement eye protection.",
                "kind": "paragraph",
                "level": 2,
                "parent_id": "safety-guide:section",
                "parent_text": "# Equipment\n\nUse replacement eye protection.",
            },
        ],
        embeddings=[[1.0, 0.0]],
    )

    assert indexed_count == 2
    assert results[0]["heading_path"] == "Safety > Equipment"
    assert results[0]["distance"] < results[1]["distance"]
    assert replacement_count == 1
    assert collection.count() == 1


def test_rag_workflow_indexes_and_answers_without_live_api(tmp_path: Path) -> None:
    """The full RAG workflow should run with local storage and fake AI results."""

    sample_path = Path(__file__).parent / "samples" / "sample.md"
    markdown = sample_path.read_text(encoding="utf-8")
    database_url = f"sqlite:///{(tmp_path / 'documents.db').as_posix()}"
    engine = build_database(database_url)
    document = DocumentRecord(
        id="9be5bc61-f338-4afb-b5af-e99837550948",
        original_name="sample.md",
        stored_path=str(sample_path),
        markdown_path=str(sample_path),
        media_type="text/markdown",
        size_bytes=sample_path.stat().st_size,
        status="ready",
    )
    save_document(engine, document)
    collection = prepare_collection(tmp_path / "chroma", "workflow_chunks")
    settings = SimpleNamespace(
        EMBEDDING_MODEL="text-embedding-3-small",
        GENERATION_MODEL="gpt-4.1-mini",
        SEMANTIC_BREAK_PERCENTILE=80,
        MIN_CHUNK_TOKENS=1,
        MAX_CHUNK_TOKENS=200,
        RAG_TOP_K=3,
    )

    units = semantic_units(markdown)
    unit_vectors = [[1.0, 0.0] for unit in units]
    expected_chunks = chunk_semantically(
        units,
        unit_vectors,
        break_percentile=80,
        min_tokens=1,
        max_tokens=200,
    )
    unit_items = []
    for index, vector in enumerate(unit_vectors):
        unit_items.append(SimpleNamespace(index=index, embedding=vector))
    chunk_items = []
    for index in range(len(expected_chunks)):
        vector = [1.0, float(index) / max(1, len(expected_chunks))]
        chunk_items.append(SimpleNamespace(index=index, embedding=vector))

    openai_client = MagicMock()
    openai_client.embeddings.create.side_effect = [
        SimpleNamespace(data=unit_items),
        SimpleNamespace(data=chunk_items),
        SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1.0, 0.0])],
        ),
    ]
    openai_client.responses.create.return_value = SimpleNamespace(
        output_text="Wear safety glasses [Source 1].",
    )

    chunks = prepare_document_for_rag(
        engine,
        collection,
        openai_client,
        document.id,
        strategy="semantic",
        settings=settings,
    )
    result = answer_document_question(
        collection,
        openai_client,
        document.id,
        "What protects a worker's eyes?",
        settings,
    )
    indexed_document = find_document(engine, document.id)

    assert len(chunks) == len(expected_chunks)
    assert collection.count() == len(expected_chunks)
    assert indexed_document is not None
    assert indexed_document.status == "indexed"
    assert indexed_document.chunking_strategy == "semantic"
    assert result["answer"] == "Wear safety glasses [Source 1]."
    assert result["sources"]
