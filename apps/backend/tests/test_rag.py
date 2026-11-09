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
    _has_document_like_acronym_context,
    _rank_bm25_chunks,
    prepare_collection,
    query_collection_chunks,
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
    assert "Never calculate" not in request["instructions"]
    assert request["store"] is False


def test_generate_grounded_answer_can_enable_strict_grounding() -> None:
    """Strict grounding should prohibit derived figures and indirect citations."""

    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="The exact figure is not stated [Source 1].",
    )

    generate_grounded_answer(
        client,
        model="gpt-4.1-mini",
        question="What is the exact figure?",
        retrieved_chunks=[{"text": "The source describes the topic."}],
        strict_grounding=True,
    )

    instructions = client.responses.create.call_args.kwargs["instructions"]
    assert "Never calculate, estimate, infer, or derive a figure" in instructions
    assert "exact requested figure is not stated" in instructions
    assert "directly support each sentence" in instructions


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


def test_answer_question_default_path_keeps_legacy_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent opt-in settings should preserve the original query and prompt calls."""

    query_mock = MagicMock(return_value=[{"id": "one", "text": "Direct fact."}])
    generation_mock = MagicMock(return_value="Direct fact [Source 1].")
    monkeypatch.setattr(rag_operations, "create_embeddings", lambda *args: [[1.0]])
    monkeypatch.setattr(rag_operations, "query_document_chunks", query_mock)
    monkeypatch.setattr(rag_operations, "generate_grounded_answer", generation_mock)
    settings = SimpleNamespace(
        EMBEDDING_MODEL="text-embedding-3-small",
        GENERATION_MODEL="gpt-4.1-mini",
        RAG_TOP_K=5,
    )

    answer_document_question(
        MagicMock(),
        MagicMock(),
        "document",
        "What is the fact?",
        settings,
        "hierarchical",
    )

    assert query_mock.call_args.args[3:] == (5, "hierarchical")
    assert query_mock.call_args.kwargs == {}
    assert generation_mock.call_args.kwargs == {}


def test_answer_question_forwards_opt_in_retrieval_and_grounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit options should reach retrieval and generation without re-indexing."""

    query_mock = MagicMock(return_value=[{"id": "one", "text": "Direct fact."}])
    generation_mock = MagicMock(return_value="Direct fact [Source 1].")
    monkeypatch.setattr(rag_operations, "create_embeddings", lambda *args: [[1.0]])
    monkeypatch.setattr(rag_operations, "query_document_chunks", query_mock)
    monkeypatch.setattr(rag_operations, "generate_grounded_answer", generation_mock)
    settings = SimpleNamespace(
        EMBEDDING_MODEL="text-embedding-3-small",
        GENERATION_MODEL="gpt-4.1-mini",
        RAG_TOP_K=5,
        RAG_RRF_K=42,
        RAG_HYBRID_CANDIDATE_MULTIPLIER=3,
    )

    answer_document_question(
        MagicMock(),
        MagicMock(),
        "document",
        "What is the fact?",
        settings,
        "hierarchical",
        retrieval_mode="hybrid",
        top_k=10,
        document_hint_mode="boost",
        strict_grounding=True,
    )

    assert query_mock.call_args.args[3:] == (10, "hierarchical")
    assert query_mock.call_args.kwargs == {
        "query_text": "What is the fact?",
        "retrieval_mode": "hybrid",
        "rrf_k": 42,
        "candidate_multiplier": 3,
        "document_hint_mode": "boost",
    }
    assert generation_mock.call_args.kwargs == {"strict_grounding": True}


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


def test_hybrid_retrieval_fuses_embedding_and_bm25_ranks(tmp_path: Path) -> None:
    """Hybrid retrieval should promote a strong keyword match through RRF."""

    collection = prepare_collection(tmp_path / "chroma", "hybrid_chunks")
    replace_document_chunks(
        collection,
        document_id="maintenance-guide",
        strategy="semantic",
        chunks=[
            {"id": "vector-first", "text": "General maintenance instructions."},
            {"id": "keyword-first", "text": "Calibrate the zephyr manifold."},
            {"id": "vector-second", "text": "Routine inspection schedule."},
        ],
        embeddings=[[1.0, 0.0], [0.0, 1.0], [0.8, 0.2]],
    )

    embedding_results = query_collection_chunks(
        collection,
        query_embedding=[1.0, 0.0],
        result_count=1,
    )
    hybrid_results = query_collection_chunks(
        collection,
        query_embedding=[1.0, 0.0],
        result_count=1,
        query_text="What does the zephyr manifold require?",
        retrieval_mode="hybrid",
        rrf_k=60,
        candidate_multiplier=4,
    )

    assert embedding_results[0]["id"] == "vector-first"
    assert "retrieval_mode" not in embedding_results[0]
    assert hybrid_results[0]["id"] == "keyword-first"
    assert hybrid_results[0]["embedding_rank"] == 3
    assert hybrid_results[0]["bm25_rank"] == 1
    assert hybrid_results[0]["retrieval_mode"] == "hybrid"


def test_hybrid_retrieval_requires_query_text(tmp_path: Path) -> None:
    """Opting into BM25 must supply the text used for keyword ranking."""

    collection = prepare_collection(tmp_path / "chroma", "hybrid_validation")

    with pytest.raises(ValueError, match="requires query text"):
        query_collection_chunks(
            collection,
            query_embedding=[1.0, 0.0],
            result_count=1,
            retrieval_mode="hybrid",
        )


def test_bm25_ties_use_stable_chunk_ids() -> None:
    """Equal keyword scores should not depend on vector-store return order."""

    chunks = [
        {"id": "chunk-z", "text": "shared keyword"},
        {"id": "chunk-a", "text": "shared keyword"},
    ]

    assert [chunk["id"] for chunk in _rank_bm25_chunks("keyword", chunks)] == [
        "chunk-a",
        "chunk-z",
    ]


def test_document_hint_can_boost_a_generic_metadata_title(tmp_path: Path) -> None:
    """A unique title mention should boost that document without hard-coded names."""

    collection = prepare_collection(tmp_path / "chroma", "hint_chunks")
    replace_document_chunks(
        collection,
        document_id="alpha",
        strategy="hierarchical",
        chunks=[
            {
                "id": "alpha:1",
                "text": "The exact maintenance interval is stated here.",
                "document_title": "Alpha Equipment Handbook",
                "document_aliases": "Alpha Equipment Handbook\nAEH",
                "source_file": "alpha_handbook.pdf",
            },
        ],
        embeddings=[[0.0, 1.0]],
    )
    replace_document_chunks(
        collection,
        document_id="beta",
        strategy="hierarchical",
        chunks=[
            {
                "id": "beta:1",
                "text": "General maintenance information.",
                "document_title": "Beta Operations Manual",
                "document_aliases": "Beta Operations Manual\nBOM",
                "source_file": "beta_manual.pdf",
            },
        ],
        embeddings=[[1.0, 0.0]],
    )

    baseline = query_collection_chunks(collection, [1.0, 0.0], 1)
    hinted = query_collection_chunks(
        collection,
        [1.0, 0.0],
        1,
        query_text="According to the Alpha Equipment Handbook, what is required?",
        document_hint_mode="boost",
        candidate_multiplier=2,
    )

    assert baseline[0]["id"] == "beta:1"
    assert hinted[0]["id"] == "alpha:1"
    assert hinted[0]["document_hint_mode"] == "boost"
    assert hinted[0]["document_hint_title"] == "Alpha Equipment Handbook"
    assert hinted[0]["document_hint_matched_name"] == "Alpha Equipment Handbook"


def test_document_hint_filter_uses_initialism_and_noops_without_match(
    tmp_path: Path,
) -> None:
    """Initialisms should filter uniquely while unmatched hints preserve ranking."""

    collection = prepare_collection(tmp_path / "chroma", "hint_filter_chunks")
    for document_id, title, alias, embedding in (
        ("first", "First Reference Manual", "FRM", [0.0, 1.0]),
        ("second", "Second Reference Manual", "SRM", [1.0, 0.0]),
    ):
        replace_document_chunks(
            collection,
            document_id=document_id,
            strategy="hierarchical",
            chunks=[
                {
                    "id": f"{document_id}:1",
                    "text": f"Material from {title}.",
                    "document_title": title,
                    "document_aliases": f"{title}\n{alias}",
                },
            ],
            embeddings=[embedding],
        )

    filtered = query_collection_chunks(
        collection,
        [1.0, 0.0],
        2,
        query_text="What does the FRM require?",
        document_hint_mode="filter",
    )
    unmatched = query_collection_chunks(
        collection,
        [1.0, 0.0],
        1,
        query_text="What is required?",
        document_hint_mode="boost",
    )

    assert [chunk["document_id"] for chunk in filtered] == ["first"]
    assert filtered[0]["document_hint_matched_name"] == "FRM"
    assert unmatched[0]["document_id"] == "second"
    assert "document_hint_mode" not in unmatched[0]


@pytest.mark.parametrize(
    "question",
    (
        "What does the 2025 NRA cover?",
        "How did the previous NRA describe the issue?",
        "What are the NRA's findings?",
        "According to the NRA, what changed?",
        "What did the NRA say about the change?",
        "NRA defines the relevant measure how?",
    ),
)
def test_document_acronym_context_accepts_named_source_uses(question: str) -> None:
    """Document-like grammar should permit a single-token acronym hint."""

    assert _has_document_like_acronym_context(question, "nra") is True


@pytest.mark.parametrize(
    "question",
    (
        "Which AML controls are described?",
        "How many AML false positives occurred?",
    ),
)
def test_document_acronym_context_rejects_topic_uses(question: str) -> None:
    """An unqualified topic acronym must not be treated as a document name."""

    assert _has_document_like_acronym_context(question, "aml") is False


def test_document_hint_ignores_an_alias_shared_by_multiple_documents(
    tmp_path: Path,
) -> None:
    """A generated short name must uniquely identify one document to apply."""

    collection = prepare_collection(tmp_path / "chroma", "ambiguous_hint_chunks")
    for document_id, title, embedding in (
        ("first", "Service Reliability Guide", [0.0, 1.0]),
        ("second", "Systems Reference Guide", [1.0, 0.0]),
    ):
        replace_document_chunks(
            collection,
            document_id=document_id,
            strategy="hierarchical",
            chunks=[
                {
                    "id": f"{document_id}:1",
                    "text": f"Material from {title}.",
                    "document_title": title,
                    "document_aliases": f"{title}\nSRG",
                },
            ],
            embeddings=[embedding],
        )

    results = query_collection_chunks(
        collection,
        [1.0, 0.0],
        1,
        query_text="What does SRG require?",
        document_hint_mode="boost",
    )

    assert results[0]["document_id"] == "second"
    assert "document_hint_mode" not in results[0]


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
    assert all(chunk["document_title"] == "Workplace Safety Guide" for chunk in chunks)
    assert all(
        chunk["document_aliases"] == "Workplace Safety Guide\nsample\nWSG"
        for chunk in chunks
    )
    assert all(chunk["page_numbers"] == [1] for chunk in chunks)
    assert result["sources"][0]["source_file"] == "sample.md"
    assert result["sources"][0]["page_numbers"] == "1"
