"""Tests for semantic and hierarchical Markdown chunking."""

from pathlib import Path

from document_rag.infrastructure.chunking.hierarchical import (
    chunk_hierarchically,
)
from document_rag.infrastructure.chunking.semantic import (
    chunk_semantically,
    semantic_units,
)


def test_semantic_units_preserve_markdown_blocks() -> None:
    """Semantic preparation should keep headings and paragraphs intact."""

    sample_path = Path(__file__).parent / "samples" / "sample.md"
    units = semantic_units(sample_path.read_text(encoding="utf-8"))

    assert units[0] == "# Workplace Safety Guide"
    assert "## Personal protective equipment" in units
    assert any("assembly point" in unit for unit in units)


def test_semantic_chunking_detects_topic_change() -> None:
    """A sharp embedding-distance change should create a chunk boundary."""

    units = [
        "Cats communicate by purring.",
        "Kittens also purr when comfortable.",
        "Databases persist application records.",
        "Database indexes improve lookup speed.",
    ]
    embeddings = [
        [1.0, 0.0],
        [0.99, 0.01],
        [0.0, 1.0],
        [0.01, 0.99],
    ]

    chunks = chunk_semantically(
        units,
        embeddings,
        break_percentile=70,
        min_tokens=1,
        max_tokens=100,
    )

    assert len(chunks) == 2
    assert "Kittens" in str(chunks[0]["text"])
    assert "Databases" not in str(chunks[0]["text"])
    assert "Databases" in str(chunks[1]["text"])


def test_hierarchical_chunking_preserves_parent_context() -> None:
    """Hierarchy leaves should retain headings and expandable parent text."""

    sample_path = Path(__file__).parent / "samples" / "sample.md"
    markdown = sample_path.read_text(encoding="utf-8")

    nodes = chunk_hierarchically(
        markdown,
        document_id="safety-guide",
        max_leaf_tokens=20,
    )
    inspection_section = None
    for node in nodes:
        if node["title"] == "Inspection":
            inspection_section = node
            break

    assert inspection_section is not None

    inspection_leaves = []
    for node in nodes:
        is_paragraph = node["kind"] == "paragraph"
        has_inspection_parent = node["parent_id"] == inspection_section["id"]
        if is_paragraph and has_inspection_parent:
            inspection_leaves.append(node)

    assert nodes[0]["kind"] == "document"
    assert inspection_section["heading_path"] == (
        "Workplace Safety Guide > Personal protective equipment > Inspection"
    )
    assert inspection_leaves
    assert all(int(node["token_count"]) <= 20 for node in inspection_leaves)
    assert "Replace damaged equipment" in str(inspection_section["text"])
    assert "assembly point" in str(nodes[0]["text"])
