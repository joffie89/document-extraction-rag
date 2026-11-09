"""Offline quality gates for the saved held-out evaluation results."""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HELDOUT_RESULT_PATHS = (
    PROJECT_ROOT / "evaluation" / "results_heldout_embedding_k5.json",
    PROJECT_ROOT / "evaluation" / "results_heldout_hybrid_k10_hint_grounded.json",
)


@pytest.mark.parametrize(
    "result_path",
    HELDOUT_RESULT_PATHS,
    ids=("embedding-k5", "hybrid-k10-hint-grounded"),
)
def test_saved_heldout_results_meet_quality_floor(result_path: Path) -> None:
    """Both saved runs must retain perfect abstention accuracy and 55% correctness."""

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    results = payload["results"]
    assert results, f"{result_path.name} contains no question results"

    not_in_documents = [
        result for result in results if result["type"] == "not-in-documents"
    ]
    assert not_in_documents, (
        f"{result_path.name} contains no not-in-documents questions"
    )

    missed_not_in_documents = [
        result["id"]
        for result in not_in_documents
        if result["judge"]["label"] != "correct"
    ]
    not_in_documents_accuracy = 1 - (
        len(missed_not_in_documents) / len(not_in_documents)
    )
    assert not_in_documents_accuracy >= 1.0, (
        f"{result_path.name} not-in-documents accuracy is "
        f"{not_in_documents_accuracy:.1%}; expected 100%. "
        f"Failures: {missed_not_in_documents}"
    )

    correct_count = sum(result["judge"]["label"] == "correct" for result in results)
    correct_rate = correct_count / len(results)
    assert correct_rate >= 0.55, (
        f"{result_path.name} correct rate is {correct_rate:.1%}; expected at least 55%"
    )
