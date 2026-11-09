"""Offline tests for the corpus evaluation runner."""

import json
from types import SimpleNamespace

import evaluate_corpus
import pytest


class FakeEndpoint:
    """Return one configured SDK-like response and record request arguments."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.response


def fake_client(
    *,
    embedding_response: object | None = None,
    response_response: object | None = None,
) -> SimpleNamespace:
    """Build the two endpoints used by the metered proxy."""

    return SimpleNamespace(
        embeddings=FakeEndpoint(
            embedding_response
            or SimpleNamespace(
                data=[SimpleNamespace(index=0, embedding=[1.0, 0.0])],
                usage=SimpleNamespace(prompt_tokens=4, total_tokens=4),
            ),
        ),
        responses=FakeEndpoint(
            response_response
            or SimpleNamespace(
                output_text="Answer [Source 1]",
                usage=SimpleNamespace(
                    input_tokens=10,
                    output_tokens=4,
                    total_tokens=14,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("page_or_section", "expected_pages"),
    [
        ("PDF page 15, Table 2.B", {15}),
        (
            "PDF pages 14-15, Table 2.B (heading and figures split across pages)",
            {14, 15},
        ),
        (
            "Strategy page 42, Improving victims' experience, paragraph 101 "
            "(PDF page 45)",
            {45},
        ),
        (
            "PDF pages 139-140, Artificial Intelligence, paragraphs 6.1-6.7",
            {139, 140},
        ),
    ],
)
def test_parse_expected_pages_uses_physical_pdf_pages(
    page_or_section: str,
    expected_pages: set[int],
) -> None:
    """PDF-labelled pages should win and ranges should expand inclusively."""

    assert evaluate_corpus.parse_expected_pages(page_or_section) == expected_pages


def test_page_parsing_and_source_page_retrieval_rank() -> None:
    """Printed strategy pages must not displace explicit physical PDF pages."""

    assert evaluate_corpus.parse_expected_pages(
        "Strategy pages 4-5, summary (PDF pages 7-8)",
    ) == {7, 8}
    chunks = [
        {
            "source_file": "other.pdf",
            "page_numbers": "7,8",
        },
        {
            "source_file": "expected.pdf",
            "page_numbers": "6-8",
        },
    ]

    result = evaluate_corpus.retrieval_score(chunks, "expected.pdf", {7, 8})

    assert result == {
        "applicable": True,
        "hit": True,
        "first_hit_rank": 2,
    }
    assert evaluate_corpus.retrieval_score(chunks, None, set()) == {
        "applicable": False,
        "hit": None,
        "first_hit_rank": None,
    }


def test_raw_retrieval_pages_prefer_leaf_over_parent_context() -> None:
    """Retrieval rank should use a leaf hit before parent pages are expanded."""

    chunk = {
        "page_numbers": "7",
        "parent_page_numbers": "7,8,9",
    }

    assert evaluate_corpus.chunk_page_numbers(chunk) == {7}


def test_collection_metadata_validation_rejects_incomplete_chunks() -> None:
    """A live run must fail before evaluation if provenance metadata is absent."""

    complete = SimpleNamespace(
        get=lambda **kwargs: {
            "metadatas": [
                {"source_file": "source.pdf", "page_numbers": "7,8"},
            ],
        },
    )
    incomplete = SimpleNamespace(
        get=lambda **kwargs: {
            "metadatas": [
                {"source_file": "source.pdf", "page_numbers": ""},
            ],
        },
    )

    assert evaluate_corpus.validate_collection_metadata(complete) == 1
    with pytest.raises(RuntimeError, match="missing source_file or page_numbers"):
        evaluate_corpus.validate_collection_metadata(incomplete)


def test_citation_scoring_checks_every_reference_and_target() -> None:
    """Missing and wrong-page citations must fail all-citations accuracy."""

    sources = [
        {"source_file": "expected.pdf", "page_numbers": "7,8"},
        {"source_file": "expected.pdf", "page_numbers": "9"},
    ]

    accurate = evaluate_corpus.citation_score(
        "Supported [Source 1] and again [1].",
        sources,
        "expected.pdf",
        {7},
    )
    inaccurate = evaluate_corpus.citation_score(
        "Wrong page [2] and missing [99].",
        sources,
        "expected.pdf",
        {7},
    )
    grouped = evaluate_corpus.citation_score(
        "One right source and one wrong page [Source 1, Source 2].",
        sources,
        "expected.pdf",
        {7},
    )

    assert accurate["all_exist"] is True
    assert accurate["all_match_expected"] is True
    assert inaccurate["all_exist"] is False
    assert inaccurate["all_match_expected"] is False
    assert inaccurate["references"][1]["exists"] is False
    assert [reference["number"] for reference in grouped["references"]] == [1, 2]
    assert grouped["all_match_expected"] is False
    assert grouped["any_match_expected"] is True


@pytest.mark.parametrize(
    ("citation", "expected_numbers"),
    [
        ("[1, 2]", [1, 2]),
        ("[Source 1, Source 2]", [1, 2]),
        ("[Sources 2, 4, 5]", [2, 4, 5]),
        ("[Source 2, 2.3]", [2]),
        ("[Source 4, section 1.1]", [4]),
    ],
)
def test_citation_numbers_support_grouped_and_annotated_forms(
    citation: str,
    expected_numbers: list[int],
) -> None:
    """Grouped citations are expanded without treating annotations as sources."""

    assert evaluate_corpus.citation_numbers(citation) == expected_numbers


def test_metered_client_uses_actual_usage_and_stops_before_overspend() -> None:
    """The hard guard must reject an unsafe request before its endpoint is called."""

    raw_client = fake_client()
    metered = evaluate_corpus.MeteredOpenAI(
        raw_client,
        guard=evaluate_corpus.CostGuard(1.0),
    )

    with metered.phase("fixture"):
        metered.embeddings.create(
            model=evaluate_corpus.EMBEDDING_MODEL,
            input=["short fixture"],
        )

    assert metered.records[0].phase == "fixture"
    assert metered.records[0].input_tokens == 4
    assert metered.records[0].used_estimate is False
    assert metered.guard.spent_usd == pytest.approx(4 * 0.02 / 1_000_000)

    blocked_client = fake_client()
    blocked = evaluate_corpus.MeteredOpenAI(
        blocked_client,
        guard=evaluate_corpus.CostGuard(0.000000001),
    )
    with pytest.raises(evaluate_corpus.CostLimitExceeded):
        blocked.responses.create(
            model=evaluate_corpus.GENERATION_MODEL,
            input="fixture",
            max_output_tokens=800,
        )
    assert blocked_client.responses.calls == []


def test_judge_uses_structured_output_and_not_in_documents_rubric() -> None:
    """The judge should be deterministic and explicitly reject fabrication."""

    judgment_response = SimpleNamespace(
        output_text=json.dumps(
            {"label": "correct", "reason": "The answer correctly abstains."},
        ),
        usage=SimpleNamespace(
            input_tokens=30,
            output_tokens=10,
            total_tokens=40,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
        ),
    )
    raw_client = fake_client(response_response=judgment_response)
    metered = evaluate_corpus.MeteredOpenAI(raw_client)
    question = {
        "id": "q999",
        "type": "not-in-documents",
        "question": "What unavailable detail is requested?",
        "expected_answer": "The documents do not cover this.",
    }

    judgment = evaluate_corpus.judge_answer(
        metered,
        question,
        "The supplied sources do not contain that detail.",
    )

    request = raw_client.responses.calls[0]
    assert judgment["label"] == "correct"
    assert request["temperature"] == 0
    assert request["model"] == "gpt-4.1-mini"
    assert request["text"]["format"]["type"] == "json_schema"
    assert "any invented answer is incorrect" in request["instructions"]
    assert "correct only if every key fact" in request["instructions"]
    assert "Missing or wrong numbers" in request["instructions"]


@pytest.mark.parametrize(
    "answer",
    [
        "The sources provided do not contain information on this topic.",
        "The provided sources do not specify the requested figure.",
        "These documents don't provide the answer.",
        "The supplied documents do not define that term.",
        "The information is not specified in the provided sources.",
        "The Economic Crime Plan does not provide a direct definition.",
        "The exact rating is not explicitly stated in the provided excerpts.",
        "The requested figure is not available from the supplied report.",
    ],
)
def test_judge_rejects_answerable_refusal_without_llm_call(answer: str) -> None:
    """A sourced question cannot receive credit for refusing to answer."""

    raw_client = fake_client()
    metered = evaluate_corpus.MeteredOpenAI(raw_client)
    question = {
        "id": "q998",
        "type": "factual",
        "question": "What figure is reported?",
        "expected_answer": "The reported figure is 42.",
        "source_file": "report.pdf",
    }

    judgment = evaluate_corpus.judge_answer(metered, question, answer)

    assert judgment == {
        "label": "incorrect",
        "reason": "refused an answerable question",
    }
    assert raw_client.responses.calls == []
    assert metered.records == []


def test_strategy_evaluation_with_fakes_and_report(tmp_path) -> None:
    """Scoring and report generation should require no network-backed client."""

    question = {
        "id": "q001",
        "question": "What protects the eyes?",
        "expected_answer": "Safety glasses.",
        "source_file": "safety.pdf",
        "page_or_section": "PDF page 7",
        "type": "factual",
    }
    retrieved = [
        {
            "id": "chunk-1",
            "text": "Safety glasses protect the eyes.",
            "source_file": "safety.pdf",
            "page_numbers": "7",
            "parent_id": "parent-1",
            "parent_text": "Safety glasses protect the eyes and face.",
            "parent_page_numbers": "7,8",
            "distance": 0.01,
            "heading_path": "Safety",
        },
        {
            "id": "chunk-2",
            "text": "A face shield protects the face.",
            "source_file": "safety.pdf",
            "page_numbers": "8",
            "parent_id": "parent-1",
            "parent_text": "Safety glasses protect the eyes and face.",
            "parent_page_numbers": "7,8",
            "distance": 0.02,
            "heading_path": "Safety",
        },
        {
            "id": "chunk-3",
            "text": "Unrelated context.",
            "source_file": "other.pdf",
            "page_numbers": "3",
            "distance": 0.03,
            "heading_path": "Other",
        },
    ]
    raw_client = fake_client()
    metered = evaluate_corpus.MeteredOpenAI(raw_client)
    settings = SimpleNamespace(
        EMBEDDING_MODEL="text-embedding-3-small",
        GENERATION_MODEL="gpt-4.1-mini",
        RAG_TOP_K=5,
    )
    temperatures = []

    def embedding_function(*args: object) -> list[list[float]]:
        return [[1.0, 0.0]]

    def query_function(*args: object) -> list[dict[str, object]]:
        return retrieved

    def answer_function(*args: object, **kwargs: object) -> str:
        temperatures.append(kwargs["temperature"])
        return "Safety glasses protect the eyes [Source 1]."

    def judge_function(*args: object) -> dict[str, str]:
        return {"label": "correct", "reason": "It matches the expected answer."}

    results = evaluate_corpus.evaluate_strategy(
        "semantic",
        object(),
        [question],
        settings,
        metered,
        embedding_function=embedding_function,
        query_function=query_function,
        answer_function=answer_function,
        judge_function=judge_function,
    )
    summary = evaluate_corpus.summarize_results(results)
    payloads = {
        strategy: {
            "results": results,
            "summary": summary,
            "run": {"indexing_usage": {"cost_usd": 0.001}},
        }
        for strategy in evaluate_corpus.STRATEGIES
    }
    report = evaluate_corpus.build_report(payloads, 0.01, 2.0)
    report_path = tmp_path / "report_v1.md"
    report_path.write_text(report, encoding="utf-8")

    assert temperatures == [0]
    assert results[0]["retrieval"]["first_hit_rank"] == 1
    assert results[0]["answer_sources"] == [
        {
            "rank": 1,
            "source_file": "safety.pdf",
            "page_numbers": [7, 8],
        },
        {"rank": 2, "source_file": "other.pdf", "page_numbers": [3]},
    ]
    assert (
        evaluate_corpus.citation_score(
            results[0]["answer"],
            results[0]["answer_sources"],
            "safety.pdf",
            {7},
        )
        == results[0]["citations"]
    )
    assert results[0]["citations"]["all_match_expected"] is True
    assert results[0]["citations"]["any_match_expected"] is True
    assert summary["correct_rate"] == 1
    assert summary["citation_any_correct_rate"] == 1
    assert summary["answerable_refusals"] == 0
    assert "## Overall results" in report
    assert "## Results by question type" in report
    assert "## Not-in-documents results" in report
    assert "## Cost and latency" in report
    assert "## Wrong or partially correct answers" in report
    assert "Indexing cost (USD)" in report


def test_strategy_evaluation_applies_opt_in_retrieval_and_grounding() -> None:
    """V2 overrides should be explicit and auditable without changing defaults."""

    question = {
        "id": "q-opt-in",
        "question": "What value does the named guide state?",
        "expected_answer": "The stated value is 42.",
        "source_file": "guide.pdf",
        "page_or_section": "PDF page 3",
        "type": "numeric",
    }
    retrieved = [
        {
            "id": "chunk-1",
            "text": "The stated value is 42.",
            "source_file": "guide.pdf",
            "page_numbers": "3",
            "distance": 0.02,
            "retrieval_mode": "hybrid",
            "embedding_rank": 2,
            "bm25_rank": 1,
            "rrf_score": 0.03,
            "document_hint_document_id": "document-1",
            "document_hint_title": "Named Guide",
            "document_hint_source_file": "guide.pdf",
            "document_hint_matched_name": "Named Guide",
        },
    ]
    settings = SimpleNamespace(
        EMBEDDING_MODEL="text-embedding-3-small",
        GENERATION_MODEL="gpt-4.1-mini",
        RAG_TOP_K=5,
    )
    query_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    answer_calls: list[dict[str, object]] = []

    def query_function(
        *args: object,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        query_calls.append((args, kwargs))
        return retrieved

    def answer_function(*args: object, **kwargs: object) -> str:
        answer_calls.append(kwargs)
        return "The stated value is 42 [Source 1]."

    results = evaluate_corpus.evaluate_strategy(
        "hierarchical",
        object(),
        [question],
        settings,
        evaluate_corpus.MeteredOpenAI(fake_client()),
        embedding_function=lambda *args: [[1.0, 0.0]],
        query_function=query_function,
        answer_function=answer_function,
        judge_function=lambda *args: {
            "label": "correct",
            "reason": "The answer includes the expected fact.",
        },
        top_k=10,
        retrieval_mode="hybrid",
        document_hint_mode="boost",
        strict_grounding=True,
        run_label="hybrid_k10_hint_grounded",
    )

    assert query_calls[0][0][2] == 10
    assert query_calls[0][1] == {
        "query_text": question["question"],
        "retrieval_mode": "hybrid",
        "rrf_k": 60,
        "candidate_multiplier": 4,
        "document_hint_mode": "boost",
    }
    assert answer_calls == [{"temperature": 0, "strict_grounding": True}]
    assert results[0]["retrieval"]["document_hint"] == {
        "mode": "boost",
        "applied": True,
        "matched_document_id": "document-1",
        "matched_title": "Named Guide",
        "matched_source_file": "guide.pdf",
        "matched_name": "Named Guide",
    }
    assert results[0]["retrieval"]["chunks"][0]["bm25_rank"] == 1
