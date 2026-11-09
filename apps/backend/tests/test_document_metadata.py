"""Tests for generic document title and alias extraction."""

from document_rag.core.document_metadata import extract_document_metadata


def test_document_metadata_prefers_first_level_one_heading() -> None:
    """A document title should come from its H1, not an earlier subsection."""

    metadata = extract_document_metadata(
        "fallback_name.pdf",
        "## Preface\n\n# **Workplace Safety Guide** (WSG)\n\nBody text.",
    )

    assert metadata["document_title"] == "Workplace Safety Guide (WSG)"
    assert metadata["document_aliases"].splitlines() == [
        "Workplace Safety Guide (WSG)",
        "fallback name",
        "WSG",
        "FN",
    ]


def test_document_metadata_uses_filename_when_markdown_has_no_heading() -> None:
    """A readable filename stem should be the title when no heading exists."""

    metadata = extract_document_metadata(
        "reference_material-2026.pdf",
        "A plain paragraph with no Markdown headings.",
    )

    assert metadata == {
        "document_title": "reference material 2026",
        "document_aliases": "reference material 2026\nreference material\nRM",
    }


def test_document_metadata_derives_short_name_and_abbreviation() -> None:
    """Short labels should be inferred mechanically from the title text."""

    metadata = extract_document_metadata(
        "response_handbook.pdf",
        "# Emergency Response Handbook (ERH): Field Edition\n",
    )

    assert metadata["document_aliases"].splitlines() == [
        "Emergency Response Handbook (ERH): Field Edition",
        "Emergency Response Handbook (ERH)",
        "response handbook",
        "ERH",
        "RH",
    ]


def test_document_metadata_removes_generic_trailing_release_labels() -> None:
    """Short aliases should omit trailing year, date, and version labels."""

    cases = (
        (
            "Operational Resilience Programme 2 2024–2027",
            "Operational Resilience Programme 2",
        ),
        ("Service Delivery Handbook March 2026", "Service Delivery Handbook"),
        ("Technical Reference Guide version 2.1", "Technical Reference Guide"),
    )

    for title, expected_alias in cases:
        metadata = extract_document_metadata("fallback.pdf", f"# {title}\n")

        assert metadata["document_title"] == title
        assert expected_alias in metadata["document_aliases"].splitlines()


def test_document_metadata_derives_leading_initialisms() -> None:
    """A long title should expose sensible leading-word acronym aliases."""

    metadata = extract_document_metadata(
        "assessment.pdf",
        "# National Resilience Assessment for Coastal Infrastructure 2025\n",
    )

    aliases = metadata["document_aliases"].splitlines()
    assert "National Resilience Assessment for Coastal Infrastructure" in aliases
    assert "NRA" in aliases
    assert "NRAC" in aliases
