"""Validate the checked-in PDF corpus and evaluation fixture."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]
CORPUS_DIRECTORY = PROJECT_ROOT / "data" / "corpus"
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions_v1.json"
REQUIRED_FIELDS = {
    "id",
    "question",
    "expected_answer",
    "source_file",
    "page_or_section",
    "type",
}
QUESTION_TYPES = {"factual", "numeric", "multi-part", "not-in-documents"}


def test_evaluation_fixture_has_required_coverage_and_valid_sources() -> None:
    """The fixture should contain 40 valid, uniquely identified questions."""

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    question_ids = [question["id"] for question in questions]
    question_types = [question["type"] for question in questions]

    assert len(questions) == 40
    assert len(question_ids) == len(set(question_ids))
    assert all(REQUIRED_FIELDS.issubset(question) for question in questions)
    assert set(question_types) == QUESTION_TYPES
    assert question_types.count("not-in-documents") >= 6

    for question in questions:
        assert question["question"].strip()
        assert question["expected_answer"].strip()
        if question["type"] == "not-in-documents":
            assert question["source_file"] is None
            assert question["page_or_section"] is None
        else:
            source_path = CORPUS_DIRECTORY / question["source_file"]
            assert source_path.is_file()
            assert source_path.suffix.casefold() == ".pdf"
            assert question["page_or_section"].strip()


def test_sources_catalogue_lists_every_pdf() -> None:
    """Every checked-in corpus PDF should appear in its provenance catalogue."""

    catalogue = (CORPUS_DIRECTORY / "SOURCES.md").read_text(encoding="utf-8")
    pdf_names = {path.name for path in CORPUS_DIRECTORY.glob("*.pdf")}

    assert len(pdf_names) == 4
    assert all(f"`{pdf_name}`" in catalogue for pdf_name in pdf_names)
    assert "Open Government Licence v3.0" in catalogue
