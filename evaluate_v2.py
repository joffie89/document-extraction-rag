"""Run the fixed v2 retrieval comparison on the development corpus fixture."""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import evaluate_corpus as v1
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent
DEVELOPMENT_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions_v1.json"
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "evaluation"
DEFAULT_RUNTIME_DIRECTORY_NAME = ".runtime_v2"
STRATEGY = "hierarchical"
JUDGE_VERSION = "v1.2"


@dataclass(frozen=True)
class EvaluationConfiguration:
    """One immutable retrieval and answer-grounding comparison."""

    slug: str
    label: str
    retrieval_mode: str
    top_k: int
    document_hint_mode: str = "none"
    strict_grounding: bool = False
    rrf_k: int = 60
    candidate_multiplier: int = 4

    def settings(self) -> dict[str, object]:
        """Return the effective settings recorded with every raw result file."""

        return asdict(self)


CONFIGURATIONS = (
    EvaluationConfiguration(
        slug="embedding_k5",
        label="Embedding k=5 (baseline)",
        retrieval_mode="embedding",
        top_k=5,
    ),
    EvaluationConfiguration(
        slug="hybrid_k5",
        label="Hybrid k=5",
        retrieval_mode="hybrid",
        top_k=5,
    ),
    EvaluationConfiguration(
        slug="hybrid_k10",
        label="Hybrid k=10",
        retrieval_mode="hybrid",
        top_k=10,
    ),
    EvaluationConfiguration(
        slug="hybrid_k10_hint_grounded",
        label="Hybrid k=10 + document hint + grounded prompt",
        retrieval_mode="hybrid",
        top_k=10,
        document_hint_mode="boost",
        strict_grounding=True,
    ),
)


def _percentage(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _number(value: object, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _table_cell(value: object) -> str:
    return " ".join(str(value).replace("|", "\\|").split())


def _label_breakdown(summary: dict[str, object]) -> str:
    return (
        f"{summary['correct']}/{summary['partially_correct']}/"
        f"{summary['incorrect']}"
    )


def _not_in_documents_breakdown(
    results: list[dict[str, object]],
) -> str:
    labels = Counter(
        str(result["judge"]["label"])
        for result in results
        if result["type"] == "not-in-documents"
    )
    return (
        f"{labels['correct']}/{labels['partially correct']}/"
        f"{labels['incorrect']}"
    )


def _answerable_refusal_ids(results: list[dict[str, object]]) -> list[str]:
    return [
        str(result["id"])
        for result in results
        if result.get("expected_source_file") is not None
        and result["judge"]["reason"] == "refused an answerable question"
    ]


def build_v2_report(
    payloads: dict[str, dict[str, object]],
    *,
    indexing_usage: dict[str, object],
    indexing_duration_seconds: float,
    total_cost_usd: float,
    cost_limit_usd: float,
) -> str:
    """Render all four configurations side by side in one Markdown report."""

    configurations = [configuration for configuration in CONFIGURATIONS]
    summaries = {
        configuration.slug: payloads[configuration.slug]["summary"]
        for configuration in configurations
    }
    labels = [configuration.label for configuration in configurations]
    lines = [
        "# RAG Evaluation Report v2",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        (
            f"Development fixture: `evaluation/questions_v1.json`; chunking: "
            f"`{STRATEGY}`; judge: `{JUDGE_VERSION}`; models: "
            f"`{v1.EMBEDDING_MODEL}` and `{v1.GENERATION_MODEL}`; "
            f"generation temperature: `0`; cost guard: `${cost_limit_usd:.2f}`."
        ),
        "",
        "The corpus was indexed once and the same hierarchical collection was "
        "used for every configuration.",
        "",
        "## Configurations",
        "",
        (
            "| Configuration | Retrieval | Top-k | Document hint | "
            "Grounding prompt | RRF k | Candidate multiplier |"
        ),
        "|---|---|---:|---|---|---:|---:|",
    ]
    for configuration in configurations:
        lines.append(
            f"| {configuration.label} | {configuration.retrieval_mode} | "
            f"{configuration.top_k} | {configuration.document_hint_mode} | "
            f"{'on' if configuration.strict_grounding else 'off'} | "
            f"{configuration.rrf_k} | {configuration.candidate_multiplier} |",
        )

    lines.extend(
        [
            "",
            "## Results side by side",
            "",
            "| Metric | " + " | ".join(labels) + " |",
            "|---|" + "---:|" * len(labels),
        ],
    )
    metrics = (
        ("Questions", "questions", str),
        ("Correct / partial / incorrect", None, _label_breakdown),
        ("Correct rate", "correct_rate", _percentage),
        ("Retrieval hit rate", "retrieval_hit_rate", _percentage),
        ("Mean first-hit rank", "mean_first_hit_rank", _number),
        ("Answerable refusals", "answerable_refusals", str),
        ("Answerable refusal rate", "answerable_refusal_rate", _percentage),
        ("Not-in-documents correct", "not_in_documents_correct", str),
        (
            "Not-in-documents correct rate",
            "not_in_documents_correct_rate",
            _percentage,
        ),
        ("Citations: all correct", "citation_accuracy_rate", _percentage),
        (
            "Citations: at least one correct",
            "citation_any_correct_rate",
            _percentage,
        ),
        ("Mean latency / question (s)", "mean_latency_seconds", _number),
        ("Total question latency (s)", "total_latency_seconds", _number),
        ("Question input tokens", "input_tokens", str),
        ("Question output tokens", "output_tokens", str),
        ("Question cost (USD)", "cost_usd", lambda value: f"${value:.6f}"),
    )
    for label, key, formatter in metrics:
        cells = []
        for configuration in configurations:
            summary = summaries[configuration.slug]
            cells.append(formatter(summary if key is None else summary[key]))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines.append(
        "| Not-in-documents C/P/I | "
        + " | ".join(
            _not_in_documents_breakdown(payloads[configuration.slug]["results"])
            for configuration in configurations
        )
        + " |",
    )

    lines.extend(
        [
            "",
            "Citation rates use sourced questions as their denominator. "
            "An answer with no parsed citation fails both citation measures.",
            "",
            "## Refusals on answerable questions",
            "",
            "| Configuration | Count | Question IDs |",
            "|---|---:|---|",
        ],
    )
    for configuration in configurations:
        refusal_ids = _answerable_refusal_ids(
            payloads[configuration.slug]["results"],
        )
        lines.append(
            f"| {configuration.label} | {len(refusal_ids)} | "
            f"{', '.join(refusal_ids) if refusal_ids else 'None'} |",
        )

    lines.extend(
        [
            "",
            "## Not-in-documents results",
            "",
            "| Configuration | ID | Label | Answer | Judge reason |",
            "|---|---|---|---|---|",
        ],
    )
    for configuration in configurations:
        for result in payloads[configuration.slug]["results"]:
            if result["type"] != "not-in-documents":
                continue
            lines.append(
                f"| {configuration.label} | {result['id']} | "
                f"{result['judge']['label']} | {_table_cell(result['answer'])} | "
                f"{_table_cell(result['judge']['reason'])} |",
            )

    lines.extend(
        [
            "",
            "## Shared indexing and total cost",
            "",
            f"- Indexing duration: `{indexing_duration_seconds:.2f}` seconds",
            f"- Indexing API cost: `${float(indexing_usage['cost_usd']):.6f}`",
            f"- Total API spend: `${total_cost_usd:.6f}`",
            f"- Cost limit: `${cost_limit_usd:.2f}`",
            "",
        ],
    )
    return "\n".join(lines)


def run_v2_evaluation(
    corpus_directory: str | Path = v1.DEFAULT_CORPUS_DIRECTORY,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    env_file: str | Path = PROJECT_ROOT / ".env",
    cost_limit_usd: float = v1.DEFAULT_COST_LIMIT_USD,
) -> dict[str, Path]:
    """Index hierarchical chunks once, run four fixed configurations, and save."""

    if cost_limit_usd <= 0:
        raise ValueError("Cost limit must be positive")
    settings = v1.load_settings(env_file, require_openai=True)
    if settings.EMBEDDING_MODEL != v1.EMBEDDING_MODEL:
        raise ValueError(f"Evaluation requires {v1.EMBEDDING_MODEL}")
    if settings.GENERATION_MODEL != v1.GENERATION_MODEL:
        raise ValueError(f"Evaluation requires {v1.GENERATION_MODEL}")

    output_root = Path(output_directory).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"
    runtime_directory = output_root / DEFAULT_RUNTIME_DIRECTORY_NAME / run_id
    raw_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=2,
    )
    client = v1.MeteredOpenAI(
        raw_client,
        guard=v1.CostGuard(cost_limit_usd),
    )

    # The development fixture is a fixed path by design. Do not discover question files.
    questions = v1.load_questions(DEVELOPMENT_QUESTIONS_PATH)
    collections, ingestion = v1.index_corpus(
        corpus_directory,
        runtime_directory,
        settings,
        client,
        strategies=(STRATEGY,),
    )
    indexing_records = [
        record for record in client.records if record.phase == f"indexing:{STRATEGY}"
    ]
    indexing_usage = v1._aggregate_usage(indexing_records)

    payloads: dict[str, dict[str, object]] = {}
    output_paths: dict[str, Path] = {}
    for configuration in CONFIGURATIONS:
        results = v1.evaluate_strategy(
            STRATEGY,
            collections[STRATEGY],
            questions,
            settings,
            client,
            top_k=configuration.top_k,
            retrieval_mode=configuration.retrieval_mode,
            rrf_k=configuration.rrf_k,
            candidate_multiplier=configuration.candidate_multiplier,
            document_hint_mode=configuration.document_hint_mode,
            strict_grounding=configuration.strict_grounding,
            run_label=configuration.slug,
        )
        payload = {
            "schema_version": 3,
            "strategy": STRATEGY,
            "configuration": configuration.settings(),
            "run": {
                "run_id": run_id,
                "corpus_directory": str(Path(corpus_directory).resolve()),
                "questions_path": str(DEVELOPMENT_QUESTIONS_PATH),
                "runtime_directory": str(runtime_directory),
                "collection_name": "evaluation_v1_hierarchical",
                "embedding_model": settings.EMBEDDING_MODEL,
                "generation_model": settings.GENERATION_MODEL,
                "temperature": 0,
                "judge_version": JUDGE_VERSION,
                "cost_limit_usd": cost_limit_usd,
                "indexing": ingestion,
                "shared_indexing_usage": indexing_usage,
            },
            "summary": v1.summarize_results(results),
            "results": results,
        }
        payloads[configuration.slug] = payload
        output_path = output_root / f"results_v2_{configuration.slug}.json"
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        output_paths[configuration.slug] = output_path

    report_path = output_root / "report_v2.md"
    report_path.write_text(
        build_v2_report(
            payloads,
            indexing_usage=indexing_usage,
            indexing_duration_seconds=float(ingestion["duration_seconds"]),
            total_cost_usd=client.guard.spent_usd,
            cost_limit_usd=cost_limit_usd,
        ),
        encoding="utf-8",
    )
    output_paths["report"] = report_path
    return output_paths


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the v2 development-set evaluation CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=v1.DEFAULT_CORPUS_DIRECTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument(
        "--cost-limit",
        type=float,
        default=v1.DEFAULT_COST_LIMIT_USD,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the v2 evaluation and print its generated artifact paths."""

    arguments = build_argument_parser().parse_args(argv)
    try:
        output_paths = run_v2_evaluation(
            arguments.corpus_dir,
            arguments.output_dir,
            arguments.env_file,
            arguments.cost_limit,
        )
    except (v1.CostLimitExceeded, OSError, RuntimeError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    for name, path in output_paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
