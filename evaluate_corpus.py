"""Evaluate both RAG chunking strategies against the checked-in corpus fixture."""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Hugging Face's cache otherwise attempts privileged symlinks on some Windows hosts.
if sys.platform == "win32":
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

from openai import OpenAI

from document_rag.application.document_operations import (
    create_document,
    process_document,
)
from document_rag.application.rag_operations import (
    build_answer_sources,
    prepare_document_for_rag,
)
from document_rag.core.config import load_settings
from document_rag.infrastructure.chroma_store import (
    prepare_collection,
    query_collection_chunks,
)
from document_rag.infrastructure.database import build_database
from document_rag.infrastructure.docling.configuration import (
    build_document_converter,
)
from document_rag.infrastructure.openai_client import (
    create_embeddings,
    generate_grounded_answer,
)
from document_rag.infrastructure.token_encoding import get_token_encoding

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_DIRECTORY = PROJECT_ROOT / "data" / "corpus"
DEFAULT_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions_v1.json"
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "evaluation"
STRATEGIES = ("hierarchical", "semantic")
GENERATION_MODEL = "gpt-4.1-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_COST_LIMIT_USD = 2.0
GENERATION_INPUT_USD_PER_MILLION = 0.40
GENERATION_CACHED_INPUT_USD_PER_MILLION = 0.10
GENERATION_OUTPUT_USD_PER_MILLION = 1.60
EMBEDDING_INPUT_USD_PER_MILLION = 0.02

PHYSICAL_PAGE_PATTERN = re.compile(
    r"\bPDF\s+pages?\s+(\d+)(?:\s*[-–]\s*(\d+))?",
    re.IGNORECASE,
)
CITATION_BRACKET_PATTERN = re.compile(r"\[([^\[\]]+)\]")
PLAIN_CITATION_LIST_PATTERN = re.compile(r"\d+(?:\s*,\s*\d+)*")
SOURCE_CITATION_LIST_PATTERN = re.compile(
    r"\bSources?\s+"
    r"(\d+(?![\d.])(?:\s*,\s*(?:Sources?\s+)?\d+(?![\d.]))*)",
    re.IGNORECASE,
)
ANSWERABLE_REFUSAL_PATTERNS = (
    re.compile(
        r"\b(?:sources?|documents?|reports?|plans?|strateg(?:y|ies)|"
        r"assessments?|excerpts?|context|material)\b.{0,100}"
        r"\b(?:do(?:es)?\s+not|don['’]t|doesn['’]t|cannot|can['’]t)\s+"
        r"(?:(?:explicitly|directly|specifically)\s+)?"
        r"(?:contain|specify|provide|define|state|detail|give|include|mention|cover)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:is|are|was|were)\s+not\s+"
        r"(?:(?:explicitly|directly|specifically)\s+)?"
        r"(?:contained|specified|provided|defined|stated|detailed|given|"
        r"included|mentioned|covered|available)\b.{0,100}"
        r"\b(?:sources?|documents?|reports?|plans?|strateg(?:y|ies)|"
        r"assessments?|excerpts?|context|material)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)
JUDGE_LABELS = {"correct", "partially correct", "incorrect"}


class CostLimitExceeded(RuntimeError):
    """Raised before an API request would exceed the configured cost limit."""


@dataclass
class CostGuard:
    """Track API spend and reject calls whose conservative estimate is unsafe."""

    limit_usd: float = DEFAULT_COST_LIMIT_USD
    spent_usd: float = 0.0

    def check(self, estimated_cost_usd: float) -> None:
        """Reject a call before sending it when its estimate exceeds the budget."""

        if estimated_cost_usd < 0:
            raise ValueError("Estimated cost cannot be negative")
        if self.spent_usd + estimated_cost_usd > self.limit_usd:
            raise CostLimitExceeded(
                "Estimated evaluation spend would exceed "
                f"${self.limit_usd:.2f} (spent ${self.spent_usd:.6f}, "
                f"next call up to ${estimated_cost_usd:.6f})",
            )

    def commit(self, cost_usd: float) -> None:
        """Record the actual or conservative fallback cost of a completed call."""

        if cost_usd < 0:
            raise ValueError("API cost cannot be negative")
        self.spent_usd += cost_usd


@dataclass
class UsageRecord:
    """One metered OpenAI request."""

    phase: str
    endpoint: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_seconds: float
    used_estimate: bool

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "phase": self.phase,
            "endpoint": self.endpoint,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "latency_seconds": self.latency_seconds,
            "used_estimate": self.used_estimate,
        }


def _object_value(value: object, name: str, default: object = 0) -> object:
    """Read one field from an SDK model, mapping, or fake test object."""

    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_int(value: object) -> int:
    """Convert optional SDK usage values to a non-negative integer."""

    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _token_count(value: object) -> int:
    """Conservatively count request text using the application's tokenizer."""

    if value is None:
        return 0
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return len(get_token_encoding().encode(text))


def _generation_cost(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate GPT-4.1 mini token cost using standard API rates."""

    cached_tokens = min(input_tokens, cached_input_tokens)
    noncached_tokens = input_tokens - cached_tokens
    return (
        noncached_tokens * GENERATION_INPUT_USD_PER_MILLION
        + cached_tokens * GENERATION_CACHED_INPUT_USD_PER_MILLION
        + output_tokens * GENERATION_OUTPUT_USD_PER_MILLION
    ) / 1_000_000


def _embedding_cost(input_tokens: int) -> float:
    """Calculate text-embedding-3-small token cost."""

    return input_tokens * EMBEDDING_INPUT_USD_PER_MILLION / 1_000_000


class _MeteredEndpoint:
    """Proxy one SDK endpoint while preserving its normal ``create`` contract."""

    def __init__(
        self,
        owner: "MeteredOpenAI",
        endpoint: object,
        endpoint_name: str,
    ) -> None:
        self._owner = owner
        self._endpoint = endpoint
        self._endpoint_name = endpoint_name

    def create(self, **kwargs: object) -> object:
        """Guard, execute, and meter one API request."""

        model = str(kwargs.get("model") or "")
        estimate = self._owner.estimate_request(self._endpoint_name, kwargs)
        self._owner.guard.check(estimate["cost_usd"])
        started = self._owner.clock()
        response = self._endpoint.create(**kwargs)
        latency = self._owner.clock() - started
        record = self._owner.usage_record(
            self._endpoint_name,
            model,
            response,
            estimate,
            latency,
        )
        self._owner.guard.commit(record.cost_usd)
        self._owner.records.append(record)
        return response

    def __getattr__(self, name: str) -> object:
        return getattr(self._endpoint, name)


@dataclass
class MeteredOpenAI:
    """OpenAI-compatible client proxy with usage accounting and a hard cost guard."""

    client: object
    guard: CostGuard = field(default_factory=CostGuard)
    clock: Callable[[], float] = time.perf_counter
    records: list[UsageRecord] = field(default_factory=list)
    _phase: str = "unscoped"

    def __post_init__(self) -> None:
        self.embeddings = _MeteredEndpoint(
            self,
            self.client.embeddings,
            "embeddings",
        )
        self.responses = _MeteredEndpoint(
            self,
            self.client.responses,
            "responses",
        )

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Assign subsequent API calls to one report phase."""

        previous = self._phase
        self._phase = name
        try:
            yield
        finally:
            self._phase = previous

    def estimate_request(
        self,
        endpoint_name: str,
        kwargs: dict[str, object],
    ) -> dict[str, object]:
        """Estimate a conservative maximum token cost before a request."""

        model = str(kwargs.get("model") or "")
        if endpoint_name == "embeddings":
            if model != EMBEDDING_MODEL:
                raise ValueError(f"No configured evaluation price for {model}")
            input_tokens = _token_count(kwargs.get("input"))
            return {
                "input_tokens": input_tokens,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": input_tokens,
                "cost_usd": _embedding_cost(input_tokens),
            }

        if model != GENERATION_MODEL:
            raise ValueError(f"No configured evaluation price for {model}")
        input_tokens = sum(
            _token_count(kwargs.get(field_name))
            for field_name in ("instructions", "input", "text")
        )
        output_tokens = _as_int(kwargs.get("max_output_tokens"))
        return {
            "input_tokens": input_tokens,
            "cached_input_tokens": 0,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": _generation_cost(input_tokens, 0, output_tokens),
        }

    def usage_record(
        self,
        endpoint_name: str,
        model: str,
        response: object,
        estimate: dict[str, object],
        latency_seconds: float,
    ) -> UsageRecord:
        """Prefer API-reported usage, falling back to the guarded estimate."""

        usage = _object_value(response, "usage", None)
        if endpoint_name == "embeddings":
            input_tokens = _as_int(_object_value(usage, "prompt_tokens", 0))
            if not input_tokens:
                input_tokens = _as_int(_object_value(usage, "input_tokens", 0))
            output_tokens = 0
            cached_tokens = 0
        else:
            input_tokens = _as_int(_object_value(usage, "input_tokens", 0))
            output_tokens = _as_int(_object_value(usage, "output_tokens", 0))
            input_details = _object_value(usage, "input_tokens_details", None)
            cached_tokens = _as_int(
                _object_value(input_details, "cached_tokens", 0),
            )

        used_estimate = usage is None or (input_tokens == 0 and output_tokens == 0)
        if used_estimate:
            input_tokens = _as_int(estimate["input_tokens"])
            cached_tokens = _as_int(estimate["cached_input_tokens"])
            output_tokens = _as_int(estimate["output_tokens"])
            cost_usd = float(estimate["cost_usd"])
        elif endpoint_name == "embeddings":
            cost_usd = _embedding_cost(input_tokens)
        else:
            cost_usd = _generation_cost(
                input_tokens,
                cached_tokens,
                output_tokens,
            )

        total_tokens = _as_int(_object_value(usage, "total_tokens", 0))
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        return UsageRecord(
            phase=self._phase,
            endpoint=endpoint_name,
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
            used_estimate=used_estimate,
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self.client, name)


def parse_expected_pages(page_or_section: str | None) -> set[int]:
    """Extract physical PDF pages, ignoring separately labelled printed pages."""

    pages: set[int] = set()
    for match in PHYSICAL_PAGE_PATTERN.finditer(page_or_section or ""):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start:
            start, end = end, start
        pages.update(range(start, end + 1))
    return pages


def chunk_page_numbers(chunk: dict[str, object]) -> set[int]:
    """Read page metadata from stored scalar or in-memory list representations."""

    value = (
        chunk.get("citation_page_numbers")
        or chunk.get("page_numbers")
        or chunk.get("parent_page_numbers")
    )
    pages: set[int] = set()
    values: list[object]
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    elif value is None:
        values = []
    else:
        values = re.split(r"\s*,\s*", str(value))

    for item in values:
        range_match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", str(item))
        if range_match:
            start, end = (int(part) for part in range_match.groups())
            if end < start:
                start, end = end, start
            pages.update(range(start, end + 1))
            continue
        try:
            pages.add(int(item))
        except (TypeError, ValueError):
            continue

    if not pages:
        start = _as_int(chunk.get("page_start"))
        end = _as_int(chunk.get("page_end")) or start
        if start:
            pages.update(range(start, max(start, end) + 1))
    return pages


def retrieval_score(
    chunks: list[dict[str, object]],
    expected_source_file: str | None,
    expected_pages: set[int],
) -> dict[str, object]:
    """Score exact source-and-page retrieval and retain the first one-based rank."""

    if expected_source_file is None:
        return {"applicable": False, "hit": None, "first_hit_rank": None}

    first_hit_rank = None
    for rank, chunk in enumerate(chunks, start=1):
        source_matches = chunk.get("source_file") == expected_source_file
        page_matches = bool(chunk_page_numbers(chunk) & expected_pages)
        if source_matches and page_matches:
            first_hit_rank = rank
            break
    return {
        "applicable": True,
        "hit": first_hit_rank is not None,
        "first_hit_rank": first_hit_rank,
    }


def citation_score(
    answer: str,
    sources: list[dict[str, object]],
    expected_source_file: str | None,
    expected_pages: set[int],
) -> dict[str, object]:
    """Validate every cited source number and its expected document/page target."""

    references = []
    for number in citation_numbers(answer):
        exists = 1 <= number <= len(sources)
        source = sources[number - 1] if exists else {}
        source_file = source.get("source_file") if exists else None
        pages = chunk_page_numbers(source) if exists else set()
        target_matches = (
            exists
            and expected_source_file is not None
            and source_file == expected_source_file
            and bool(pages & expected_pages)
        )
        references.append(
            {
                "number": number,
                "exists": exists,
                "source_file": source_file,
                "page_numbers": sorted(pages),
                "matches_expected": target_matches,
            },
        )

    all_exist = bool(references) and all(
        bool(reference["exists"]) for reference in references
    )
    target_applicable = expected_source_file is not None
    all_match = None
    any_match = None
    if target_applicable:
        all_match = bool(references) and all(
            bool(reference["matches_expected"]) for reference in references
        )
        any_match = bool(references) and any(
            bool(reference["matches_expected"]) for reference in references
        )
    return {
        "references": references,
        "all_exist": all_exist,
        "target_applicable": target_applicable,
        "all_match_expected": all_match,
        "any_match_expected": any_match,
    }


def citation_numbers(answer: str) -> list[int]:
    """Extract source indexes from supported citation bracket forms."""

    numbers = []
    for bracket in CITATION_BRACKET_PATTERN.finditer(answer):
        content = bracket.group(1).strip()
        if PLAIN_CITATION_LIST_PATTERN.fullmatch(content):
            numbers.extend(int(value) for value in re.findall(r"\d+", content))
            continue

        for source_list in SOURCE_CITATION_LIST_PATTERN.finditer(content):
            numbers.extend(
                int(value) for value in re.findall(r"\d+", source_list.group(1))
            )
    return numbers


def judge_answer(
    client: object,
    question: dict[str, object],
    answer: str,
    model: str = GENERATION_MODEL,
) -> dict[str, str]:
    """Use a deterministic structured-output judge for semantic correctness."""

    expected_source = str(question.get("source_file") or "").strip()
    answerable = bool(expected_source) and question.get("type") != "not-in-documents"
    if answerable and any(
        pattern.search(answer) for pattern in ANSWERABLE_REFUSAL_PATTERNS
    ):
        return {
            "label": "incorrect",
            "reason": "refused an answerable question",
        }

    response = client.responses.create(
        model=model,
        instructions=(
            "Compare the candidate answer with the expected answer for semantic "
            "correctness. Label it correct, partially correct, or incorrect. "
            "Label an answer correct only if every key fact in the expected "
            "answer is present and accurate, even if phrased differently. "
            "Missing or wrong numbers must be labelled partially correct or "
            "incorrect, never correct. A partially correct answer has a material "
            "omission or minor factual error. For a not-in-documents question, "
            "correct means "
            "the candidate clearly says the supplied documents or sources do not "
            "contain the answer; any invented answer is incorrect. Give one brief "
            "sentence explaining the label."
        ),
        input=(
            f"Question type: {question['type']}\n"
            f"Question: {question['question']}\n"
            f"Expected answer: {question['expected_answer']}\n"
            f"Candidate answer: {answer}"
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "answer_judgment",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "enum": sorted(JUDGE_LABELS),
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["label", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        max_output_tokens=200,
        temperature=0,
        store=False,
    )
    try:
        judgment = json.loads(str(response.output_text))
    except (AttributeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Judge returned invalid JSON") from exc
    label = str(judgment.get("label") or "").casefold()
    reason = " ".join(str(judgment.get("reason") or "").split())
    if label not in JUDGE_LABELS or not reason:
        raise RuntimeError("Judge returned an invalid label or empty reason")
    return {"label": label, "reason": reason}


def _serialize_chunk(chunk: dict[str, object], rank: int) -> dict[str, object]:
    """Keep the raw retrieval evidence needed to audit one result."""

    serialized = {
        "rank": rank,
        "id": str(chunk.get("id") or ""),
        "text": str(chunk.get("text") or ""),
        "distance": float(chunk.get("distance") or 0),
        "source_file": chunk.get("source_file"),
        "page_numbers": sorted(chunk_page_numbers(chunk)),
        "heading_path": str(chunk.get("heading_path") or ""),
        "kind": str(chunk.get("kind") or ""),
    }
    for field_name in (
        "retrieval_mode",
        "embedding_rank",
        "bm25_rank",
        "bm25_score",
        "rrf_score",
        "document_hint_rank",
        "document_hint_mode",
        "document_hint_document_id",
        "document_hint_title",
        "document_hint_source_file",
        "document_hint_matched_name",
    ):
        if field_name in chunk:
            serialized[field_name] = chunk[field_name]
    return serialized


def _serialize_answer_sources(
    sources: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Keep every prompt source in the exact order used by answer citations."""

    return [
        {
            "rank": rank,
            "source_file": source.get("source_file"),
            "page_numbers": sorted(chunk_page_numbers(source)),
        }
        for rank, source in enumerate(sources, start=1)
    ]


def _aggregate_usage(records: list[UsageRecord]) -> dict[str, object]:
    """Sum token, latency, and cost fields for a set of metered calls."""

    return {
        "input_tokens": sum(record.input_tokens for record in records),
        "cached_input_tokens": sum(record.cached_input_tokens for record in records),
        "output_tokens": sum(record.output_tokens for record in records),
        "total_tokens": sum(record.total_tokens for record in records),
        "cost_usd": sum(record.cost_usd for record in records),
        "api_latency_seconds": sum(record.latency_seconds for record in records),
        "calls": [record.as_dict() for record in records],
    }


def load_questions(
    path: str | Path = DEFAULT_QUESTIONS_PATH,
) -> list[dict[str, object]]:
    """Load, validate, and return the immutable evaluation fixture."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Evaluation questions must be a non-empty JSON list")
    required = {
        "id",
        "question",
        "expected_answer",
        "source_file",
        "page_or_section",
        "type",
    }
    for question in payload:
        if not isinstance(question, dict) or not required.issubset(question):
            raise ValueError("Each evaluation question is missing required fields")
    return payload


def discover_pdfs(corpus_directory: str | Path) -> list[Path]:
    """Return corpus PDFs in deterministic relative-path order."""

    root = Path(corpus_directory).expanduser().resolve()
    pdfs = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".pdf"
        ),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    if not pdfs:
        raise ValueError(f"No PDFs were found in {root}")
    return pdfs


def validate_collection_metadata(collection: object) -> int:
    """Ensure every indexed chunk retains a source file and physical PDF pages."""

    stored = collection.get(include=["metadatas"])
    metadatas = list(stored.get("metadatas") or [])
    if not metadatas:
        raise RuntimeError("Evaluation collection contains no chunks")
    invalid_ordinals = [
        ordinal
        for ordinal, metadata in enumerate(metadatas)
        if not str((metadata or {}).get("source_file") or "").strip()
        or not chunk_page_numbers(dict(metadata or {}))
    ]
    if invalid_ordinals:
        raise RuntimeError(
            "Indexed chunks are missing source_file or page_numbers metadata: "
            + ", ".join(str(ordinal) for ordinal in invalid_ordinals[:10]),
        )
    return len(metadatas)


def index_corpus(
    corpus_directory: str | Path,
    runtime_directory: Path,
    settings: object,
    client: MeteredOpenAI,
    *,
    strategies: Sequence[str] = STRATEGIES,
) -> tuple[dict[str, object], dict[str, object]]:
    """Extract through Docling and index each document into fresh collections."""

    selected_strategies = tuple(strategies)
    if not selected_strategies or any(
        strategy not in STRATEGIES for strategy in selected_strategies
    ):
        raise ValueError("Evaluation strategies must be hierarchical or semantic")

    engine = build_database(
        f"sqlite:///{(runtime_directory / 'documents.db').as_posix()}",
    )
    converter = build_document_converter(
        settings.EXTRACTION_TIMEOUT_SECONDS,
        settings.OCR_LANGUAGE,
    )
    collections = {
        strategy: prepare_collection(
            runtime_directory / "chroma" / strategy,
            f"evaluation_v1_{strategy}",
        )
        for strategy in selected_strategies
    }
    corpus_root = Path(corpus_directory).expanduser().resolve()
    documents = []
    started = time.perf_counter()
    collection_chunk_counts = {}
    try:
        for pdf_path in discover_pdfs(corpus_root):
            relative_path = pdf_path.relative_to(corpus_root).as_posix()
            with pdf_path.open("rb") as source:
                document = create_document(
                    engine,
                    relative_path,
                    "application/pdf",
                    source,
                    runtime_directory / "uploads",
                    settings.MAX_UPLOAD_BYTES,
                )
            document = process_document(
                engine,
                converter,
                document.id,
                runtime_directory / "markdown",
                settings.MAX_UPLOAD_BYTES,
                settings.MAX_DOCUMENT_PAGES,
            )
            chunk_counts = {}
            for strategy in selected_strategies:
                with client.phase(f"indexing:{strategy}"):
                    chunks = prepare_document_for_rag(
                        engine,
                        collections[strategy],
                        client,
                        document.id,
                        strategy,
                        settings,
                    )
                chunk_counts[strategy] = len(chunks)
            documents.append(
                {
                    "document_id": document.id,
                    "source_file": relative_path,
                    "chunk_counts": chunk_counts,
                },
            )
        collection_chunk_counts = {
            strategy: validate_collection_metadata(collection)
            for strategy, collection in collections.items()
        }
    finally:
        engine.dispose()
    return collections, {
        "documents": documents,
        "collection_chunk_counts": collection_chunk_counts,
        "duration_seconds": time.perf_counter() - started,
    }


def evaluate_strategy(
    strategy: str,
    collection: object,
    questions: list[dict[str, object]],
    settings: object,
    client: MeteredOpenAI,
    *,
    embedding_function: Callable[..., list[list[float]]] = create_embeddings,
    query_function: Callable[..., list[dict[str, object]]] = (query_collection_chunks),
    answer_source_function: Callable[
        [list[dict[str, object]]],
        list[dict[str, object]],
    ] = build_answer_sources,
    answer_function: Callable[..., str] = generate_grounded_answer,
    judge_function: Callable[..., dict[str, str]] = judge_answer,
    clock: Callable[[], float] = time.perf_counter,
    top_k: int | None = None,
    retrieval_mode: str = "embedding",
    rrf_k: int = 60,
    candidate_multiplier: int = 4,
    document_hint_mode: str = "none",
    strict_grounding: bool = False,
    run_label: str | None = None,
) -> list[dict[str, object]]:
    """Run every fixture question through one collection and chunking strategy."""

    effective_top_k = int(settings.RAG_TOP_K if top_k is None else top_k)
    if effective_top_k < 1:
        raise ValueError("Retrieval depth must be positive")
    if retrieval_mode not in {"embedding", "hybrid"}:
        raise ValueError("Retrieval mode must be embedding or hybrid")
    if document_hint_mode not in {"none", "boost", "filter"}:
        raise ValueError("Document hint mode must be none, boost, or filter")
    phase_label = run_label or strategy
    results = []
    for position, question in enumerate(questions, start=1):
        print(
            f"[{phase_label} {position}/{len(questions)}] {question['id']}: "
            f"{question['question']}",
            flush=True,
        )
        usage_start = len(client.records)
        total_started = clock()

        retrieval_started = clock()
        with client.phase(f"question:{phase_label}:{question['id']}:retrieval"):
            query_embedding = embedding_function(
                client,
                [str(question["question"])],
                settings.EMBEDDING_MODEL,
            )[0]
        if retrieval_mode == "embedding" and document_hint_mode == "none":
            retrieved = query_function(
                collection,
                query_embedding,
                effective_top_k,
            )
        else:
            retrieved = query_function(
                collection,
                query_embedding,
                effective_top_k,
                query_text=str(question["question"]),
                retrieval_mode=retrieval_mode,
                rrf_k=rrf_k,
                candidate_multiplier=candidate_multiplier,
                document_hint_mode=document_hint_mode,
            )
        retrieval_latency = clock() - retrieval_started
        answer_sources = answer_source_function(retrieved)

        answer_started = clock()
        with client.phase(f"question:{phase_label}:{question['id']}:answer"):
            answer_arguments: dict[str, object] = {"temperature": 0}
            if strict_grounding:
                answer_arguments["strict_grounding"] = True
            answer = answer_function(
                client,
                settings.GENERATION_MODEL,
                str(question["question"]),
                answer_sources,
                **answer_arguments,
            )
        answer_latency = clock() - answer_started

        judge_started = clock()
        with client.phase(f"question:{phase_label}:{question['id']}:judge"):
            judgment = judge_function(
                client,
                question,
                answer,
                settings.GENERATION_MODEL,
            )
        judge_latency = clock() - judge_started

        expected_source = question.get("source_file")
        expected_source_file = (
            str(expected_source) if expected_source is not None else None
        )
        expected_pages = parse_expected_pages(
            str(question.get("page_or_section") or ""),
        )
        retrieval = retrieval_score(
            retrieved,
            expected_source_file,
            expected_pages,
        )
        retrieval["chunks"] = [
            _serialize_chunk(chunk, rank)
            for rank, chunk in enumerate(retrieved, start=1)
        ]
        if document_hint_mode != "none":
            hinted_chunk = next(
                (
                    chunk
                    for chunk in retrieved
                    if chunk.get("document_hint_document_id") is not None
                ),
                None,
            )
            retrieval["document_hint"] = {
                "mode": document_hint_mode,
                "applied": hinted_chunk is not None,
                "matched_document_id": (
                    hinted_chunk.get("document_hint_document_id")
                    if hinted_chunk is not None
                    else None
                ),
                "matched_title": (
                    hinted_chunk.get("document_hint_title")
                    if hinted_chunk is not None
                    else None
                ),
                "matched_source_file": (
                    hinted_chunk.get("document_hint_source_file")
                    if hinted_chunk is not None
                    else None
                ),
                "matched_name": (
                    hinted_chunk.get("document_hint_matched_name")
                    if hinted_chunk is not None
                    else None
                ),
            }
        citations = citation_score(
            answer,
            answer_sources,
            expected_source_file,
            expected_pages,
        )
        usage = _aggregate_usage(client.records[usage_start:])
        results.append(
            {
                "id": question["id"],
                "type": question["type"],
                "question": question["question"],
                "expected_answer": question["expected_answer"],
                "expected_source_file": expected_source_file,
                "expected_pages": sorted(expected_pages),
                "retrieval": retrieval,
                "answer": answer,
                "answer_sources": _serialize_answer_sources(answer_sources),
                "judge": judgment,
                "citations": citations,
                "latency_seconds": {
                    "retrieval": retrieval_latency,
                    "answer": answer_latency,
                    "judge": judge_latency,
                    "total": clock() - total_started,
                },
                "usage": usage,
            },
        )
    return results


def summarize_results(results: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate answer, retrieval, citation, latency, token, and cost metrics."""

    labels = Counter(str(result["judge"]["label"]) for result in results)
    retrieval_results = [
        result for result in results if bool(result["retrieval"]["applicable"])
    ]
    citation_results = [
        result for result in results if bool(result["citations"]["target_applicable"])
    ]
    answerable_results = [
        result for result in results if result.get("expected_source_file") is not None
    ]
    not_in_documents_results = [
        result for result in results if result.get("type") == "not-in-documents"
    ]
    hit_ranks = [
        int(result["retrieval"]["first_hit_rank"])
        for result in retrieval_results
        if result["retrieval"]["first_hit_rank"] is not None
    ]
    result_count = len(results)
    return {
        "questions": result_count,
        "correct": labels["correct"],
        "partially_correct": labels["partially correct"],
        "incorrect": labels["incorrect"],
        "correct_rate": labels["correct"] / result_count if result_count else 0,
        "retrieval_applicable": len(retrieval_results),
        "retrieval_hits": sum(
            bool(result["retrieval"]["hit"]) for result in retrieval_results
        ),
        "retrieval_hit_rate": (
            sum(bool(result["retrieval"]["hit"]) for result in retrieval_results)
            / len(retrieval_results)
            if retrieval_results
            else None
        ),
        "mean_first_hit_rank": (sum(hit_ranks) / len(hit_ranks) if hit_ranks else None),
        "citation_applicable": len(citation_results),
        "citation_accurate": sum(
            result["citations"]["all_match_expected"] is True
            for result in citation_results
        ),
        "citation_accuracy_rate": (
            sum(
                result["citations"]["all_match_expected"] is True
                for result in citation_results
            )
            / len(citation_results)
            if citation_results
            else None
        ),
        "citation_any_correct": sum(
            result["citations"]["any_match_expected"] is True
            for result in citation_results
        ),
        "citation_any_correct_rate": (
            sum(
                result["citations"]["any_match_expected"] is True
                for result in citation_results
            )
            / len(citation_results)
            if citation_results
            else None
        ),
        "answerable_refusals": sum(
            result["judge"]["reason"] == "refused an answerable question"
            for result in answerable_results
        ),
        "answerable_refusal_rate": (
            sum(
                result["judge"]["reason"] == "refused an answerable question"
                for result in answerable_results
            )
            / len(answerable_results)
            if answerable_results
            else None
        ),
        "not_in_documents_questions": len(not_in_documents_results),
        "not_in_documents_correct": sum(
            result["judge"]["label"] == "correct" for result in not_in_documents_results
        ),
        "not_in_documents_correct_rate": (
            sum(
                result["judge"]["label"] == "correct"
                for result in not_in_documents_results
            )
            / len(not_in_documents_results)
            if not_in_documents_results
            else None
        ),
        "mean_latency_seconds": (
            sum(float(result["latency_seconds"]["total"]) for result in results)
            / result_count
            if result_count
            else 0
        ),
        "total_latency_seconds": sum(
            float(result["latency_seconds"]["total"]) for result in results
        ),
        "input_tokens": sum(int(result["usage"]["input_tokens"]) for result in results),
        "cached_input_tokens": sum(
            int(result["usage"]["cached_input_tokens"]) for result in results
        ),
        "output_tokens": sum(
            int(result["usage"]["output_tokens"]) for result in results
        ),
        "total_tokens": sum(int(result["usage"]["total_tokens"]) for result in results),
        "cost_usd": sum(float(result["usage"]["cost_usd"]) for result in results),
    }


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
    """Format correct/partial/incorrect counts compactly for report tables."""

    return f"{summary['correct']}/{summary['partially_correct']}/{summary['incorrect']}"


def build_report(
    payloads: dict[str, dict[str, object]],
    total_cost_usd: float,
    cost_limit_usd: float,
) -> str:
    """Render the requested side-by-side Markdown evaluation report."""

    summaries = {strategy: payload["summary"] for strategy, payload in payloads.items()}
    indexing_costs = {
        strategy: float(
            payload.get("run", {}).get("indexing_usage", {}).get("cost_usd", 0),
        )
        for strategy, payload in payloads.items()
    }
    total_strategy_costs = {
        strategy: indexing_costs[strategy] + float(summaries[strategy]["cost_usd"])
        for strategy in STRATEGIES
    }
    lines = [
        "# RAG Evaluation Report v1",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        (
            f"Models: `{EMBEDDING_MODEL}` and `{GENERATION_MODEL}`; "
            "generation temperature: `0`; "
            f"cost guard: `${cost_limit_usd:.2f}`."
        ),
        "",
        "Citation accuracy is reported over sourced questions only; "
        "not-in-documents questions have no expected document/page target.",
        "",
        "## Overall results",
        "",
        "| Metric | Hierarchical | Semantic |",
        "|---|---:|---:|",
    ]
    overall_metrics = [
        ("Questions", "questions", str),
        ("Correct", "correct", str),
        ("Partially correct", "partially_correct", str),
        ("Incorrect", "incorrect", str),
        ("Correct rate", "correct_rate", _percentage),
        ("Retrieval hit rate", "retrieval_hit_rate", _percentage),
        ("Mean first-hit rank", "mean_first_hit_rank", _number),
        ("Citation accuracy", "citation_accuracy_rate", _percentage),
    ]
    for label, key, formatter in overall_metrics:
        lines.append(
            f"| {label} | {formatter(summaries['hierarchical'][key])} | "
            f"{formatter(summaries['semantic'][key])} |",
        )

    question_types = sorted(
        {
            str(result["type"])
            for payload in payloads.values()
            for result in payload["results"]
        },
    )
    lines.extend(
        [
            "",
            "## Results by question type",
            "",
            (
                "| Type | H C/P/I | S C/P/I | H correct | S correct | "
                "H retrieval | S retrieval | H citations | S citations |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ],
    )
    for question_type in question_types:
        type_summaries = {}
        for strategy, payload in payloads.items():
            type_summaries[strategy] = summarize_results(
                [
                    result
                    for result in payload["results"]
                    if result["type"] == question_type
                ],
            )
        hierarchical = type_summaries["hierarchical"]
        semantic = type_summaries["semantic"]
        lines.append(
            f"| {question_type} | {_label_breakdown(hierarchical)} | "
            f"{_label_breakdown(semantic)} | "
            f"{_percentage(hierarchical['correct_rate'])} | "
            f"{_percentage(semantic['correct_rate'])} | "
            f"{_percentage(hierarchical['retrieval_hit_rate'])} | "
            f"{_percentage(semantic['retrieval_hit_rate'])} | "
            f"{_percentage(hierarchical['citation_accuracy_rate'])} | "
            f"{_percentage(semantic['citation_accuracy_rate'])} |",
        )

    lines.extend(
        [
            "",
            "## Not-in-documents results",
            "",
            (
                "| Strategy | ID | Label | Answer | Judge reason | "
                "Latency (s) | Cost (USD) |"
            ),
            "|---|---|---|---|---|---:|---:|",
        ],
    )
    for strategy in STRATEGIES:
        for result in payloads[strategy]["results"]:
            if result["type"] != "not-in-documents":
                continue
            lines.append(
                f"| {strategy} | {result['id']} | {result['judge']['label']} | "
                f"{_table_cell(result['answer'])} | "
                f"{_table_cell(result['judge']['reason'])} | "
                f"{float(result['latency_seconds']['total']):.2f} | "
                f"${float(result['usage']['cost_usd']):.6f} |",
            )

    lines.extend(
        [
            "",
            "## Cost and latency",
            "",
            "| Metric | Hierarchical | Semantic |",
            "|---|---:|---:|",
        ],
    )
    for label, key, formatter in (
        ("Mean latency / question (s)", "mean_latency_seconds", _number),
        ("Total question latency (s)", "total_latency_seconds", _number),
        ("Input tokens", "input_tokens", str),
        ("Cached input tokens", "cached_input_tokens", str),
        ("Output tokens", "output_tokens", str),
        ("Total tokens", "total_tokens", str),
        ("Question cost (USD)", "cost_usd", lambda value: f"${value:.6f}"),
    ):
        lines.append(
            f"| {label} | {formatter(summaries['hierarchical'][key])} | "
            f"{formatter(summaries['semantic'][key])} |",
        )
    lines.append(
        f"| Indexing cost (USD) | ${indexing_costs['hierarchical']:.6f} | "
        f"${indexing_costs['semantic']:.6f} |",
    )
    lines.append(
        "| Total strategy cost (USD) | "
        f"${total_strategy_costs['hierarchical']:.6f} | "
        f"${total_strategy_costs['semantic']:.6f} |",
    )
    lines.extend(
        [
            "",
            f"Total evaluation spend including indexing: **${total_cost_usd:.6f}**.",
            "",
            "## Wrong or partially correct answers",
            "",
        ],
    )
    failures = [
        (strategy, result)
        for strategy in STRATEGIES
        for result in payloads[strategy]["results"]
        if result["judge"]["label"] != "correct"
    ]
    if not failures:
        lines.append("None.")
    for strategy, result in failures:
        lines.extend(
            [
                f"### {result['id']} — {strategy} — {result['judge']['label']}",
                "",
                f"**Question:** {result['question']}",
                "",
                f"**Answer:** {result['answer']}",
                "",
                f"**Expected:** {result['expected_answer']}",
                "",
                f"**Judge reason:** {result['judge']['reason']}",
                "",
            ],
        )
    return "\n".join(lines).rstrip() + "\n"


def run_evaluation(
    corpus_directory: str | Path = DEFAULT_CORPUS_DIRECTORY,
    questions_path: str | Path = DEFAULT_QUESTIONS_PATH,
    output_directory: str | Path = DEFAULT_OUTPUT_DIRECTORY,
    env_file: str | Path = PROJECT_ROOT / ".env",
    cost_limit_usd: float = DEFAULT_COST_LIMIT_USD,
) -> dict[str, Path]:
    """Index once per strategy, run all questions, and save raw and summary files."""

    if cost_limit_usd <= 0:
        raise ValueError("Cost limit must be positive")
    settings = load_settings(env_file, require_openai=True)
    if settings.EMBEDDING_MODEL != EMBEDDING_MODEL:
        raise ValueError(f"Evaluation requires {EMBEDDING_MODEL}")
    if settings.GENERATION_MODEL != GENERATION_MODEL:
        raise ValueError(f"Evaluation requires {GENERATION_MODEL}")

    output_root = Path(output_directory).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"
    runtime_directory = output_root / ".runtime_v1" / run_id
    raw_client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=2,
    )
    metered_client = MeteredOpenAI(
        raw_client,
        guard=CostGuard(cost_limit_usd),
    )
    questions = load_questions(questions_path)
    collections, ingestion = index_corpus(
        corpus_directory,
        runtime_directory,
        settings,
        metered_client,
    )

    payloads = {}
    output_paths = {}
    for strategy in STRATEGIES:
        results = evaluate_strategy(
            strategy,
            collections[strategy],
            questions,
            settings,
            metered_client,
        )
        indexing_records = [
            record
            for record in metered_client.records
            if record.phase == f"indexing:{strategy}"
        ]
        payload = {
            "schema_version": 2,
            "strategy": strategy,
            "run": {
                "run_id": run_id,
                "corpus_directory": str(Path(corpus_directory).resolve()),
                "questions_path": str(Path(questions_path).resolve()),
                "runtime_directory": str(runtime_directory),
                "collection_name": f"evaluation_v1_{strategy}",
                "top_k": settings.RAG_TOP_K,
                "embedding_model": settings.EMBEDDING_MODEL,
                "generation_model": settings.GENERATION_MODEL,
                "temperature": 0,
                "cost_limit_usd": cost_limit_usd,
                "indexing": ingestion,
                "indexing_usage": _aggregate_usage(indexing_records),
            },
            "summary": summarize_results(results),
            "results": results,
        }
        payloads[strategy] = payload
        output_path = output_root / f"results_v1_{strategy}.json"
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        output_paths[strategy] = output_path

    report_path = output_root / "report_v1.md"
    report_path.write_text(
        build_report(
            payloads,
            metered_client.guard.spent_usd,
            cost_limit_usd,
        ),
        encoding="utf-8",
    )
    output_paths["report"] = report_path
    return output_paths


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the corpus-evaluation CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIRECTORY)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument(
        "--cost-limit",
        type=float,
        default=DEFAULT_COST_LIMIT_USD,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run evaluation and print the three generated artifact paths."""

    arguments = build_argument_parser().parse_args(argv)
    try:
        output_paths = run_evaluation(
            arguments.corpus_dir,
            arguments.questions,
            arguments.output_dir,
            arguments.env_file,
            arguments.cost_limit,
        )
    except (CostLimitExceeded, OSError, RuntimeError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    for name, path in output_paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
