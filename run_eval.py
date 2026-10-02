"""
Automatically run every question in the eval CSV against your local RAG app
and fill in the model_answer column for you.

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

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


def run_eval(csv_path, document_id):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    for i, row in enumerate(rows, start=1):
        question = row["question"].strip()
        if not question:
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
            print(f"    -> {answer[:100]}...")
        except Exception as e:
            row["model_answer"] = f"ERROR: {e}"
            print(f"    -> ERROR: {e}")

    out_path = csv_path.replace(".csv", "_answered.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Answers saved to: {out_path}")
    print("Now open that file, compare model_answer vs true_answer for each row,")
    print("and fill in the 'verdict' column yourself before running score_eval.py.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_eval.py <csv_path> <document_id>")
        sys.exit(1)
    run_eval(sys.argv[1], sys.argv[2])
