"""Tests for the local CSV evaluation runner."""

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import run_eval


def test_run_eval_writes_a_non_empty_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful fixture evaluation should classify its result."""

    fixture_path = tmp_path / "fixture.csv"
    fieldnames = [
        "question",
        "true_answer",
        "model_answer",
        "verdict",
    ]
    with fixture_path.open("w", newline="", encoding="utf-8") as fixture_file:
        writer = csv.DictWriter(fixture_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "question": "What protects workers' eyes?",
                "true_answer": "Safety glasses.",
                "model_answer": "",
                "verdict": "",
            },
        )

    response = MagicMock()
    response.json.return_value = {"answer": "Safety glasses."}
    post = MagicMock(return_value=response)
    monkeypatch.setattr(run_eval.requests, "post", post)

    output_path = run_eval.run_eval(fixture_path, "document-id")

    with output_path.open(newline="", encoding="utf-8") as output_file:
        result = next(csv.DictReader(output_file))

    assert result["model_answer"] == "Safety glasses."
    assert result["verdict"] == "PASS"
    post.assert_called_once_with(
        f"{run_eval.BASE_URL}/documents/document-id/ask",
        json={"question": "What protects workers' eyes?"},
        timeout=60,
    )
