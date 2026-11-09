"""Offline tests for the fixed v2 development-set evaluation."""

import json
from pathlib import Path
from types import SimpleNamespace

import evaluate_v2
import pytest


def _result(
    question_id: str,
    *,
    question_type: str = "factual",
    label: str = "correct",
    reason: str = "All expected facts are present.",
    expected_source_file: str | None = "guide.pdf",
) -> dict[str, object]:
    """Build a complete, minimal saved result for report tests."""

    return {
        "id": question_id,
        "type": question_type,
        "question": "What does the guide say?",
        "expected_answer": "It says the required fact.",
        "expected_source_file": expected_source_file,
        "expected_pages": [3],
        "retrieval": {
            "applicable": expected_source_file is not None,
            "hit": True if expected_source_file is not None else None,
            "first_hit_rank": 1 if expected_source_file is not None else None,
            "chunks": [],
        },
        "answer": "The required fact is stated [Source 1].",
        "answer_sources": [],
        "judge": {"label": label, "reason": reason},
        "citations": {
            "references": [],
            "all_exist": True,
            "target_applicable": expected_source_file is not None,
            "all_match_expected": (True if expected_source_file is not None else None),
            "any_match_expected": (True if expected_source_file is not None else None),
        },
        "latency_seconds": {
            "retrieval": 0.1,
            "answer": 0.2,
            "judge": 0.3,
            "total": 0.6,
        },
        "usage": {
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost_usd": 0.001,
            "api_latency_seconds": 0.5,
            "calls": [],
        },
    }


def _fake_results() -> list[dict[str, object]]:
    return [
        _result("q001"),
        _result(
            "q002",
            question_type="not-in-documents",
            reason="The answer correctly says the documents do not cover it.",
            expected_source_file=None,
        ),
    ]


def test_configuration_matrix_is_fixed_and_records_every_option() -> None:
    """The comparison must run only the four requested configurations."""

    assert [configuration.slug for configuration in evaluate_v2.CONFIGURATIONS] == [
        "embedding_k5",
        "hybrid_k5",
        "hybrid_k10",
        "hybrid_k10_hint_grounded",
    ]
    assert [configuration.top_k for configuration in evaluate_v2.CONFIGURATIONS] == [
        5,
        5,
        10,
        10,
    ]
    assert evaluate_v2.CONFIGURATIONS[0].retrieval_mode == "embedding"
    assert evaluate_v2.CONFIGURATIONS[-1].settings() == {
        "slug": "hybrid_k10_hint_grounded",
        "label": "Hybrid k=10 + document hint + grounded prompt",
        "retrieval_mode": "hybrid",
        "top_k": 10,
        "document_hint_mode": "boost",
        "strict_grounding": True,
        "rrf_k": 60,
        "candidate_multiplier": 4,
    }


def test_v2_report_contains_requested_comparisons() -> None:
    """The report should expose both citation measures and all requested outcomes."""

    payloads = {
        configuration.slug: {
            "summary": evaluate_v2.v1.summarize_results(_fake_results()),
            "results": _fake_results(),
        }
        for configuration in evaluate_v2.CONFIGURATIONS
    }
    report = evaluate_v2.build_v2_report(
        payloads,
        indexing_usage={"cost_usd": 0.0001},
        indexing_duration_seconds=1.25,
        total_cost_usd=0.05,
        cost_limit_usd=2.0,
    )

    assert "Embedding k=5 (baseline)" in report
    assert "Hybrid k=10 + document hint + grounded prompt" in report
    assert "Retrieval hit rate" in report
    assert "Correct rate" in report
    assert "Answerable refusals" in report
    assert "Not-in-documents results" in report
    assert "Citations: all correct" in report
    assert "Citations: at least one correct" in report
    assert "Question cost (USD)" in report
    assert "Total API spend" in report


def test_run_indexes_once_and_passes_each_configuration_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Orchestration should share one hierarchy and never need a live endpoint."""

    loaded_paths = []
    index_calls = []
    evaluation_calls = []
    settings = SimpleNamespace(
        EMBEDDING_MODEL=evaluate_v2.v1.EMBEDDING_MODEL,
        GENERATION_MODEL=evaluate_v2.v1.GENERATION_MODEL,
        OPENAI_API_KEY="offline-test-key",
        OPENAI_TIMEOUT_SECONDS=1,
    )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = SimpleNamespace()
            self.responses = SimpleNamespace()

    def load_questions(path: Path) -> list[dict[str, object]]:
        loaded_paths.append(Path(path))
        return [{"id": "q001"}]

    def index_corpus(*args: object, **kwargs: object):
        index_calls.append((args, kwargs))
        return {"hierarchical": object()}, {
            "documents": [],
            "collection_chunk_counts": {"hierarchical": 1},
            "duration_seconds": 1.0,
        }

    def evaluate_strategy(*args: object, **kwargs: object):
        evaluation_calls.append((args, kwargs))
        return _fake_results()

    monkeypatch.setattr(evaluate_v2.v1, "load_settings", lambda *a, **k: settings)
    monkeypatch.setattr(evaluate_v2.v1, "load_questions", load_questions)
    monkeypatch.setattr(evaluate_v2.v1, "index_corpus", index_corpus)
    monkeypatch.setattr(evaluate_v2.v1, "evaluate_strategy", evaluate_strategy)
    monkeypatch.setattr(evaluate_v2, "OpenAI", FakeOpenAI)

    output_paths = evaluate_v2.run_v2_evaluation(
        corpus_directory=tmp_path / "corpus",
        output_directory=tmp_path / "output",
        env_file=tmp_path / ".env",
        cost_limit_usd=2.0,
    )

    assert loaded_paths == [evaluate_v2.DEVELOPMENT_QUESTIONS_PATH]
    assert len(index_calls) == 1
    assert index_calls[0][1]["strategies"] == ("hierarchical",)
    assert len(evaluation_calls) == 4
    assert [call[1]["run_label"] for call in evaluation_calls] == [
        configuration.slug for configuration in evaluate_v2.CONFIGURATIONS
    ]
    assert [call[1]["top_k"] for call in evaluation_calls] == [5, 5, 10, 10]
    assert evaluation_calls[-1][1]["document_hint_mode"] == "boost"
    assert evaluation_calls[-1][1]["strict_grounding"] is True

    assert set(output_paths) == {
        "embedding_k5",
        "hybrid_k5",
        "hybrid_k10",
        "hybrid_k10_hint_grounded",
        "report",
    }
    for path in output_paths.values():
        assert path.is_file()
    baseline = json.loads(output_paths["embedding_k5"].read_text(encoding="utf-8"))
    assert baseline["configuration"]["retrieval_mode"] == "embedding"
    assert baseline["configuration"]["top_k"] == 5
    assert baseline["run"]["judge_version"] == "v1.2"
    assert baseline["run"]["cost_limit_usd"] == 2.0
