"""Tests for vector indexing, retrieval, and grounded generation."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import document_rag.application.rag_operations as rag_operations
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


def test_answer_sources_keep_retrieval_order_and_prompt_passages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returned source n should be the exact passage numbered n in the prompt."""

    retrieved_chunks = [
        {
            "id": "document:b-child",
            "parent_id": "document:b-parent",
            "parent_text": "Expanded passage B.",
            "text": "Child passage B.",
            "heading_path": "Section B",
            "ordinal": 9,
        },
        {
            "id": "document:a-child",
            "parent_id": "document:a-parent",
            "parent_text": "Expanded passage A.",
            "text": "Child passage A.",
            "heading_path": "Section A",
            "ordinal": 1,
        },
    ]
    monkeypatch.setattr(
        rag_operations,
        "create_embeddings",
        lambda *args: [[1.0, 0.0]],
    )
    monkeypatch.setattr(
        rag_operations,
        "query_document_chunks",
        lambda *args: retrieved_chunks,
    )
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="Use passage B [Source 1], then A [Source 2].",
    )

    result = answer_document_question(
        MagicMock(),
        client,
        "document",
        "Which passage applies?",
        SimpleNamespace(
            EMBEDDING_MODEL="text-embedding-3-small",
            GENERATION_MODEL="gpt-4.1-mini",
            RAG_TOP_K=2,
        ),
    )

    prompt = client.responses.create.call_args.kwargs["input"]
    assert [source["id"] for source in result["sources"]] == [
        "document:b-child",
        "document:a-child",
    ]
    assert [source["text"] for source in result["sources"]] == [
        "Expanded passage B.",
        "Expanded passage A.",
    ]
    assert prompt.index("[Source 1] Section B\nExpanded passage B.") < prompt.index(
        "[Source 2] Section A\nExpanded passage A.",
    )


def test_answer_sources_deduplicate_retrieved_chunks_with_the_same_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate child hits must not shift later citation numbers."""

    retrieved_chunks = [
        {
            "id": "document:b-child-2",
            "parent_id": "document:b-parent",
            "parent_text": "Expanded passage B.",
            "text": "Second child from B.",
            "heading_path": "Section B",
        },
        {
            "id": "document:b-child-1",
            "parent_id": "document:b-parent",
            "parent_text": "Expanded passage B.",
            "text": "First child from B.",
            "heading_path": "Section B",
        },
        {
            "id": "document:a-child",
            "parent_id": "document:a-parent",
            "parent_text": "Expanded passage A.",
            "text": "Child from A.",
            "heading_path": "Section A",
        },
    ]
    monkeypatch.setattr(
        rag_operations,
        "create_embeddings",
        lambda *args: [[1.0, 0.0]],
    )
    monkeypatch.setattr(
        rag_operations,
        "query_document_chunks",
        lambda *args: retrieved_chunks,
    )
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="Passage A is cited as [Source 2].",
    )

    result = answer_document_question(
        MagicMock(),
        client,
        "document",
        "What does A say?",
        SimpleNamespace(
            EMBEDDING_MODEL="text-embedding-3-small",
            GENERATION_MODEL="gpt-4.1-mini",
            RAG_TOP_K=3,
        ),
    )

    prompt = client.responses.create.call_args.kwargs["input"]
    assert [source["id"] for source in result["sources"]] == [
        "document:b-child-2",
        "document:a-child",
    ]
    assert prompt.count("[Source 1]") == 1
    assert prompt.count("[Source 2]") == 1
    assert "[Source 2] Section A\nExpanded passage A." in prompt


def test_chroma_keeps_both_strategies_and_replaces_them_independently(
    tmp_path: Path,
) -> None:
    """Each strategy should remain queryable and replace only its own chunks."""

    collection = prepare_collection(tmp_path / "chroma", "test_chunks")
    chunks = [
        {
            "text": "Safety glasses protect the eyes.",
            "ordinal": 0,
            "kind": "semantic",
            "level": 0,
            "heading_path": "Safety > Equipment",
            "source_file": "safety.pdf",
            "page_numbers": [2, 3],
        },
        {
            "text": "Evacuate when the alarm sounds.",
            "ordinal": 1,
            "kind": "semantic",
            "level": 0,
            "heading_path": "Safety > Emergencies",
            "source_file": "safety.pdf",
            "page_numbers": [4],
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
        strategy="semantic",
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
                "source_file": "safety.pdf",
                "page_numbers": [5],
                "parent_page_numbers": [5, 6],
            },
        ],
        embeddings=[[1.0, 0.0]],
    )
    hierarchical_results = query_document_chunks(
        collection,
        document_id="safety-guide",
        query_embedding=[1.0, 0.0],
        result_count=2,
        strategy="hierarchical",
    )
    semantic_results = query_document_chunks(
        collection,
        document_id="safety-guide",
        query_embedding=[1.0, 0.0],
        result_count=2,
        strategy="semantic",
    )
    semantic_replacement_count = replace_document_chunks(
        collection,
        document_id="safety-guide",
        strategy="semantic",
        chunks=[
            {
                "text": "Updated semantic eye-protection guidance.",
                "kind": "semantic",
                "level": 0,
            },
        ],
        embeddings=[[1.0, 0.0]],
    )
    updated_semantic_results = query_document_chunks(
        collection,
        document_id="safety-guide",
        query_embedding=[1.0, 0.0],
        result_count=2,
        strategy="semantic",
    )
    preserved_hierarchical_results = query_document_chunks(
        collection,
        document_id="safety-guide",
        query_embedding=[1.0, 0.0],
        result_count=2,
        strategy="hierarchical",
    )

    assert indexed_count == 2
    assert results[0]["heading_path"] == "Safety > Equipment"
    assert results[0]["source_file"] == "safety.pdf"
    assert results[0]["page_numbers"] == "2,3"
    assert results[0]["page_start"] == 2
    assert results[0]["page_end"] == 3
    assert results[0]["distance"] < results[1]["distance"]
    assert replacement_count == 1
    assert hierarchical_results[0]["strategy"] == "hierarchical"
    assert hierarchical_results[0]["parent_page_numbers"] == "5,6"
    assert all(result["strategy"] == "semantic" for result in semantic_results)
    assert semantic_replacement_count == 1
    assert updated_semantic_results[0]["text"] == (
        "Updated semantic eye-protection guidance."
    )
    assert preserved_hierarchical_results[0]["text"] == (
        "Use replacement eye protection."
    )
    assert collection.count() == 2


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
    replace_document_chunks(
        collection,
        document.id,
        strategy="hierarchical",
        chunks=[
            {
                "id": f"{document.id}:stale",
                "text": "Stale guidance from before a Markdown edit.",
                "kind": "paragraph",
                "level": 1,
            },
        ],
        embeddings=[[1.0, 0.0]],
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
        strategy="semantic",
    )
    indexed_document = find_document(engine, document.id)
    stale_results = query_document_chunks(
        collection,
        document.id,
        query_embedding=[1.0, 0.0],
        result_count=1,
        strategy="hierarchical",
    )

    assert len(chunks) == len(expected_chunks)
    assert collection.count() == len(expected_chunks)
    assert indexed_document is not None
    assert indexed_document.status == "indexed"
    assert indexed_document.chunking_strategy == "semantic"
    assert stale_results == []
    assert result["answer"] == "Wear safety glasses [Source 1]."
    assert result["sources"]
    assert all(chunk["source_file"] == "sample.md" for chunk in chunks)
    assert all(chunk["page_numbers"] == [1] for chunk in chunks)
    assert result["sources"][0]["source_file"] == "sample.md"
    assert result["sources"][0]["page_numbers"] == "1"
