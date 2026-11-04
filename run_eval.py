"""
Automatically run every question in the eval CSV against your local RAG app
and fill in the model_answer and verdict columns.

Usage:
    python run_eval.py rag_eval_filled.csv <document_id>

Example:
    python run_eval.py rag_eval_filled.csv 1e3d9e2f-7c03-462d-9a80-2fd792fdee5b

Requires: pip install requests
Your app must already be running (uvicorn) and the document already indexed
(status "indexed") before you run this.
"""

import csv
import sys
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def _normalize_answer(answer: str) -> str:
    """Normalize insignificant whitespace and case for exact-match scoring."""

    return " ".join(answer.casefold().split())


def _answer_verdict(answer: str, expected_answer: str) -> str:
    """Classify exact matches without pretending to judge paraphrases."""

    if not answer:
        return "EMPTY_ANSWER"
    if expected_answer and _normalize_answer(answer) == _normalize_answer(
        expected_answer,
    ):
        return "PASS"
    return "ANSWERED"


def run_eval(csv_path: str | Path, document_id: str) -> Path:
    """Run the fixture against the local API and write an answered CSV."""

    rows = []
    input_path = Path(csv_path)
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append(row)

    for required_field in ("model_answer", "verdict"):
        if required_field not in fieldnames:
            fieldnames.append(required_field)

    for i, row in enumerate(rows, start=1):
        question = row.get("question", "").strip()
        if not question:
            row["model_answer"] = ""
            row["verdict"] = "SKIPPED"
            continue

        print(f"[{i}/{len(rows)}] Asking: {question}")

        try:
            resp = requests.post(
                f"{BASE_URL}/documents/{document_id}/ask",
                json={"question": question},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "").replace("\n", " ").strip()
            row["model_answer"] = answer
            row["verdict"] = _answer_verdict(
                answer,
                row.get("true_answer", "").strip(),
            )
            print(f"    -> {answer[:100]}...")
        except Exception as e:
            row["model_answer"] = f"ERROR: {e}"
            row["verdict"] = "ERROR"
            print(f"    -> ERROR: {e}")

    out_path = input_path.with_name(
        f"{input_path.stem}_answered{input_path.suffix or '.csv'}",
    )
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Answers saved to: {out_path}")
    print("PASS means an exact normalized match. Review ANSWERED rows for semantic")
    print("equivalence; EMPTY_ANSWER, ERROR, and SKIPPED are execution outcomes.")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_eval.py <csv_path> <document_id>")
        sys.exit(1)
    run_eval(sys.argv[1], sys.argv[2])
