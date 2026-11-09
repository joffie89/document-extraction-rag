"""Persist and query OpenAI vectors with local ChromaDB."""

import math
import re
from collections import Counter
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

_BM25_K1 = 1.5
_BM25_B = 0.75
_DEFAULT_RRF_K = 60
_DEFAULT_CANDIDATE_MULTIPLIER = 4
_TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)
_ACRONYM_LEAD_INS = frozenset(
    {
        "current",
        "earlier",
        "latest",
        "previous",
        "prior",
        "the",
        "this",
    }
)
_REPORTING_WORDS = frozenset(
    {
        "conclude",
        "concludes",
        "concluded",
        "define",
        "defines",
        "defined",
        "describe",
        "describes",
        "described",
        "estimate",
        "estimates",
        "estimated",
        "find",
        "finds",
        "found",
        "identify",
        "identifies",
        "identified",
        "list",
        "lists",
        "listed",
        "note",
        "notes",
        "noted",
        "provide",
        "provides",
        "provided",
        "recommend",
        "recommends",
        "recommended",
        "report",
        "reports",
        "reported",
        "say",
        "says",
        "said",
        "specify",
        "specifies",
        "specified",
        "state",
        "states",
        "stated",
    }
)
_FOUR_DIGIT_YEAR = re.compile(r"^(?:19|20)\d{2}$")


def _page_numbers(value: object) -> list[int]:
    """Normalize chunk page metadata for scalar Chroma storage."""

    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = []

    return sorted({int(page) for page in candidates if str(page).strip()})


def prepare_collection(
    chroma_directory: str | Path,
    collection_name: str,
) -> Collection:
    """Open a persistent cosine-distance collection without an embedder."""

    if len(collection_name.strip()) < 3:
        raise ValueError("The Chroma collection name must have at least 3 characters")

    storage_path = Path(chroma_directory).expanduser().resolve()
    storage_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(storage_path),
        settings=Settings(anonymized_telemetry=False),
    )

    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}},
    )


def delete_document_chunks(
    collection: Collection,
    document_id: str,
) -> None:
    """Delete every stored strategy for one document."""

    collection.delete(where={"document_id": document_id})


def replace_document_chunks(
    collection: Collection,
    document_id: str,
    strategy: str,
    chunks: list[dict[str, object]],
    embeddings: list[list[float]],
) -> int:
    """Replace one document strategy's vectors with a complete chunk set."""

    if strategy not in {"semantic", "hierarchical"}:
        raise ValueError("Chunking strategy must be semantic or hierarchical")
    if len(chunks) != len(embeddings):
        raise ValueError("Each indexed chunk requires one embedding")

    strategy_filter = {
        "$and": [
            {"document_id": document_id},
            {"strategy": strategy},
        ],
    }
    collection.delete(where=strategy_filter)
    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        text = str(chunk.get("text") or "").strip()
        if not text:
            raise ValueError("Indexed chunks cannot be blank")

        chunk_id = str(chunk.get("id") or f"{document_id}:{strategy}:{index}")
        parent_id = str(chunk.get("parent_id") or "")
        metadata: dict[str, str | int] = {
            "document_id": document_id,
            "strategy": strategy,
            "ordinal": int(chunk.get("ordinal", index)),
            "kind": str(chunk.get("kind") or strategy),
            "level": int(chunk.get("level", 0)),
            "heading_path": str(chunk.get("heading_path") or ""),
            "parent_id": parent_id,
        }
        parent_text = str(chunk.get("parent_text") or "").strip()
        if parent_text:
            metadata["parent_text"] = parent_text
        source_file = str(chunk.get("source_file") or "").strip()
        if source_file:
            metadata["source_file"] = source_file
        for field_name in ("document_title", "document_aliases"):
            field_value = str(chunk.get(field_name) or "").strip()
            if field_value:
                metadata[field_name] = field_value
        pages = _page_numbers(chunk.get("page_numbers"))
        if pages:
            metadata["page_numbers"] = ",".join(str(page) for page in pages)
            metadata["page_start"] = pages[0]
            metadata["page_end"] = pages[-1]
        parent_pages = _page_numbers(chunk.get("parent_page_numbers"))
        if parent_pages:
            metadata["parent_page_numbers"] = ",".join(
                str(page) for page in parent_pages
            )

        ids.append(chunk_id)
        documents.append(text)
        metadatas.append(metadata)

    if len(ids) != len(set(ids)):
        raise ValueError("Chunk identifiers must be unique")

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


def query_document_chunks(
    collection: Collection,
    document_id: str,
    query_embedding: list[float],
    result_count: int,
    strategy: str | None = None,
    *,
    query_text: str | None = None,
    retrieval_mode: str = "embedding",
    rrf_k: int = _DEFAULT_RRF_K,
    candidate_multiplier: int = _DEFAULT_CANDIDATE_MULTIPLIER,
    document_hint_mode: str = "none",
) -> list[dict[str, object]]:
    """Retrieve chunks for one document, optionally fusing vector and BM25 ranks."""

    if strategy is not None and strategy not in {"semantic", "hierarchical"}:
        raise ValueError("Chunking strategy must be semantic or hierarchical")

    where: dict[str, object] = {"document_id": document_id}
    if strategy is not None:
        where = {
            "$and": [
                {"document_id": document_id},
                {"strategy": strategy},
            ],
        }

    return _retrieve_chunks(
        collection,
        query_embedding,
        result_count,
        where=where,
        query_text=query_text,
        retrieval_mode=retrieval_mode,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        document_hint_mode=document_hint_mode,
    )


def query_collection_chunks(
    collection: Collection,
    query_embedding: list[float],
    result_count: int,
    *,
    query_text: str | None = None,
    retrieval_mode: str = "embedding",
    rrf_k: int = _DEFAULT_RRF_K,
    candidate_multiplier: int = _DEFAULT_CANDIDATE_MULTIPLIER,
    document_hint_mode: str = "none",
) -> list[dict[str, object]]:
    """Retrieve collection chunks, optionally fusing vector and BM25 ranks."""

    return _retrieve_chunks(
        collection,
        query_embedding,
        result_count,
        query_text=query_text,
        retrieval_mode=retrieval_mode,
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        document_hint_mode=document_hint_mode,
    )


def _retrieve_chunks(
    collection: Collection,
    query_embedding: list[float],
    result_count: int,
    *,
    where: dict[str, object] | None = None,
    query_text: str | None = None,
    retrieval_mode: str = "embedding",
    rrf_k: int = _DEFAULT_RRF_K,
    candidate_multiplier: int = _DEFAULT_CANDIDATE_MULTIPLIER,
    document_hint_mode: str = "none",
) -> list[dict[str, object]]:
    """Dispatch to the unchanged vector path or opt-in hybrid retrieval."""

    if document_hint_mode not in {"none", "boost", "filter"}:
        raise ValueError("Document hint mode must be none, boost, or filter")
    if document_hint_mode != "none" and (query_text is None or not query_text.strip()):
        raise ValueError("Document hints require query text")
    if rrf_k < 1:
        raise ValueError("The RRF rank constant must be positive")
    if candidate_multiplier < 1:
        raise ValueError("The candidate multiplier must be positive")

    hint = None
    effective_where = where
    if document_hint_mode != "none" and query_text is not None:
        hint = _match_document_hint(collection, query_text, where=where)
        if hint is not None and document_hint_mode == "filter":
            effective_where = _combine_where(
                where,
                {"document_id": str(hint["document_id"])},
            )

    if retrieval_mode == "embedding":
        candidate_count = result_count
        if hint is not None and document_hint_mode == "boost":
            candidate_count *= candidate_multiplier
        chunks = _query_chunks(
            collection,
            query_embedding,
            candidate_count,
            where=effective_where,
        )
        if hint is not None and document_hint_mode == "boost":
            chunks = _boost_document_hint(chunks, hint, rrf_k=rrf_k)
        return _annotate_document_hint(chunks[:result_count], hint, document_hint_mode)
    if retrieval_mode != "hybrid":
        raise ValueError("Retrieval mode must be embedding or hybrid")
    if query_text is None or not query_text.strip():
        raise ValueError("Hybrid retrieval requires query text")

    candidate_count = result_count * candidate_multiplier
    embedding_chunks = _query_chunks(
        collection,
        query_embedding,
        candidate_count,
        where=effective_where,
    )
    bm25_chunks = _query_bm25_chunks(
        collection,
        query_text,
        candidate_count,
        where=effective_where,
    )
    chunks = _reciprocal_rank_fusion(
        embedding_chunks,
        bm25_chunks,
        candidate_count if document_hint_mode == "boost" else result_count,
        rrf_k=rrf_k,
    )
    if hint is not None and document_hint_mode == "boost":
        chunks = _boost_document_hint(chunks, hint, rrf_k=rrf_k)
    return _annotate_document_hint(chunks[:result_count], hint, document_hint_mode)


def _combine_where(
    existing: dict[str, object] | None,
    added: dict[str, object],
) -> dict[str, object]:
    """Combine a generated document filter with an existing Chroma filter."""

    if existing is None:
        return added
    return {"$and": [existing, added]}


def _match_document_hint(
    collection: Collection,
    query_text: str,
    *,
    where: dict[str, object] | None = None,
) -> dict[str, object] | None:
    """Resolve one unambiguous document name mentioned in the query."""

    get_arguments: dict[str, object] = {"include": ["metadatas"]}
    if where is not None:
        get_arguments["where"] = where
    stored = collection.get(**get_arguments)
    documents: dict[str, dict[str, object]] = {}
    for raw_metadata in stored.get("metadatas") or []:
        metadata = dict(raw_metadata or {})
        document_id = str(metadata.get("document_id") or "").strip()
        if document_id:
            documents.setdefault(document_id, metadata)

    query_tokens = _tokenize(query_text)
    matches = []
    for document_id, metadata in documents.items():
        title = str(metadata.get("document_title") or "").strip()
        source_file = str(metadata.get("source_file") or "").strip()
        aliases = [
            alias.strip()
            for alias in str(metadata.get("document_aliases") or "").splitlines()
            if alias.strip()
        ]
        filename = source_file.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
        filename_alias = " ".join(re.sub(r"[_-]+", " ", Path(filename).stem).split())
        names = list(dict.fromkeys([title, *aliases, filename_alias]))
        best = None
        for name in names:
            name_tokens = _tokenize(name)
            if not name_tokens or not _contains_token_phrase(query_tokens, name_tokens):
                continue
            if len(name_tokens) == 1:
                is_initialism = name.isupper() and 2 <= len(name) <= 10
                is_full_title = name.casefold() == title.casefold() and len(name) >= 5
                if not (is_initialism or is_full_title):
                    continue
                if is_initialism and not _has_document_like_acronym_context(
                    query_text,
                    name_tokens[0],
                ):
                    continue
            score = (len(name_tokens), len(name))
            if best is None or score > best[0]:
                best = (score, name)
        if best is not None:
            matches.append(
                {
                    "document_id": document_id,
                    "document_title": title,
                    "source_file": source_file,
                    "matched_name": best[1],
                    "match_score": best[0],
                }
            )

    if not matches:
        return None
    matches.sort(key=lambda item: item["match_score"], reverse=True)
    if len(matches) > 1 and matches[0]["match_score"] == matches[1]["match_score"]:
        return None
    return matches[0]


def _contains_token_phrase(tokens: list[str], phrase: list[str]) -> bool:
    """Return whether a normalized token phrase occurs contiguously."""

    width = len(phrase)
    return any(tokens[index : index + width] == phrase for index in range(len(tokens)))


def _has_document_like_acronym_context(query_text: str, acronym: str) -> bool:
    """Distinguish a named-document acronym from an ordinary topic term."""

    if re.search(
        rf"(?<!\w){re.escape(acronym)}[\u2019']s\b",
        query_text,
        flags=re.IGNORECASE,
    ):
        return True

    tokens = _tokenize(query_text)
    for index, token in enumerate(tokens):
        if token != acronym:
            continue

        previous = tokens[index - 1] if index else ""
        if previous in _ACRONYM_LEAD_INS or _FOUR_DIGIT_YEAR.fullmatch(previous):
            return True

        preceding = tokens[max(0, index - 3) : index]
        if len(preceding) >= 2 and preceding[-2:] == ["according", "to"]:
            return True
        if len(preceding) >= 3 and preceding[-3:] == ["according", "to", "the"]:
            return True

        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if following in _REPORTING_WORDS:
            return True

    return False


def _boost_document_hint(
    chunks: list[dict[str, object]],
    hint: dict[str, object],
    *,
    rrf_k: int,
) -> list[dict[str, object]]:
    """Add a third reciprocal-rank signal for chunks from a named document."""

    scored = []
    hint_rank = 0
    for rank, chunk in enumerate(chunks, start=1):
        base_score = float(chunk.get("rrf_score") or (1 / (rrf_k + rank)))
        if str(chunk.get("document_id") or "") == str(hint["document_id"]):
            hint_rank += 1
            base_score += 1 / (rrf_k + hint_rank)
            chunk = dict(chunk)
            chunk["document_hint_rank"] = hint_rank
        scored.append((base_score, rank, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _, _, chunk in scored]


def _annotate_document_hint(
    chunks: list[dict[str, object]],
    hint: dict[str, object] | None,
    mode: str,
) -> list[dict[str, object]]:
    """Attach auditable hint resolution metadata to returned chunks."""

    if hint is None:
        return chunks
    annotated = []
    for chunk in chunks:
        item = dict(chunk)
        item["document_hint_mode"] = mode
        item["document_hint_document_id"] = hint["document_id"]
        item["document_hint_title"] = hint["document_title"]
        item["document_hint_source_file"] = hint["source_file"]
        item["document_hint_matched_name"] = hint["matched_name"]
        annotated.append(item)
    return annotated


def _tokenize(text: str) -> list[str]:
    """Tokenize arbitrary Unicode text for case-insensitive keyword search."""

    return [match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(text)]


def _query_bm25_chunks(
    collection: Collection,
    query_text: str,
    result_count: int,
    *,
    where: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """Rank locally stored chunks with BM25, honoring the vector query filter."""

    get_arguments: dict[str, object] = {
        "include": ["documents", "metadatas"],
    }
    if where is not None:
        get_arguments["where"] = where

    results = collection.get(**get_arguments)
    ids = results.get("ids") or []
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    chunks = []

    for index, text in enumerate(documents):
        metadata = dict(metadatas[index] or {})
        metadata["id"] = ids[index]
        metadata["text"] = text
        chunks.append(metadata)

    return _rank_bm25_chunks(query_text, chunks)[:result_count]


def _rank_bm25_chunks(
    query_text: str,
    chunks: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Return positive-scoring BM25 matches in deterministic score order."""

    query_terms = list(dict.fromkeys(_tokenize(query_text)))
    if not query_terms or not chunks:
        return []

    tokenized_chunks = []
    document_frequencies: Counter[str] = Counter()
    for chunk in chunks:
        heading = str(chunk.get("heading_path") or "").strip()
        text = str(chunk.get("text") or "")
        tokens = _tokenize(f"{heading}\n{text}" if heading else text)
        tokenized_chunks.append(tokens)
        document_frequencies.update(set(tokens))

    average_length = sum(map(len, tokenized_chunks)) / len(tokenized_chunks)
    if average_length == 0:
        return []

    corpus_size = len(chunks)
    scored_chunks = []
    for ordinal, (chunk, tokens) in enumerate(
        zip(chunks, tokenized_chunks, strict=True)
    ):
        term_frequencies = Counter(tokens)
        document_length = len(tokens)
        score = 0.0

        for term in query_terms:
            frequency = term_frequencies[term]
            if frequency == 0:
                continue
            document_frequency = document_frequencies[term]
            inverse_document_frequency = math.log(
                1
                + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            length_normalization = _BM25_K1 * (
                1 - _BM25_B + _BM25_B * document_length / average_length
            )
            score += inverse_document_frequency * (
                frequency * (_BM25_K1 + 1) / (frequency + length_normalization)
            )

        if score > 0:
            scored_chunk = dict(chunk)
            scored_chunk["bm25_score"] = score
            # Chroma does not promise a meaningful order for ``get`` results.
            # Use the stable chunk identifier before the incidental collection
            # order so equal BM25 scores yield reproducible ranks and RRF scores.
            scored_chunks.append(
                (score, str(scored_chunk.get("id") or ""), ordinal, scored_chunk)
            )

    scored_chunks.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [chunk for _, _, _, chunk in scored_chunks]


def _reciprocal_rank_fusion(
    embedding_chunks: list[dict[str, object]],
    bm25_chunks: list[dict[str, object]],
    result_count: int,
    *,
    rrf_k: int,
) -> list[dict[str, object]]:
    """Fuse vector and BM25 ranks with equal-weight reciprocal rank fusion."""

    fused: dict[str, dict[str, object]] = {}
    for rank_name, chunks in (
        ("embedding_rank", embedding_chunks),
        ("bm25_rank", bm25_chunks),
    ):
        for rank, chunk in enumerate(chunks, start=1):
            chunk_id = str(chunk["id"])
            fused_chunk = fused.setdefault(chunk_id, dict(chunk))
            for key, value in chunk.items():
                fused_chunk.setdefault(key, value)
            fused_chunk[rank_name] = rank
            fused_chunk["rrf_score"] = float(fused_chunk.get("rrf_score") or 0) + (
                1 / (rrf_k + rank)
            )

    def ranking_key(chunk: dict[str, object]) -> tuple[object, ...]:
        embedding_rank = float(chunk.get("embedding_rank") or math.inf)
        bm25_rank = float(chunk.get("bm25_rank") or math.inf)
        return (
            -float(chunk["rrf_score"]),
            min(embedding_rank, bm25_rank),
            embedding_rank,
            bm25_rank,
            str(chunk["id"]),
        )

    ranked_chunks = sorted(fused.values(), key=ranking_key)
    for chunk in ranked_chunks:
        chunk["retrieval_mode"] = "hybrid"
    return ranked_chunks[:result_count]


def _query_chunks(
    collection: Collection,
    query_embedding: list[float],
    result_count: int,
    *,
    where: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """Run one validated nearest-neighbour query with an optional filter."""

    if not query_embedding:
        raise ValueError("A query embedding is required")
    if result_count < 1:
        raise ValueError("The result count must be positive")

    collection_size = collection.count()
    if collection_size == 0:
        return []

    query_arguments: dict[str, object] = {
        "query_embeddings": [query_embedding],
        "n_results": min(result_count, collection_size),
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        query_arguments["where"] = where

    results = collection.query(
        **query_arguments,
    )
    ids = results.get("ids") or [[]]
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    retrieved_chunks = []

    for index, text in enumerate(documents[0]):
        metadata = dict(metadatas[0][index] or {})
        metadata["id"] = ids[0][index]
        metadata["text"] = text
        metadata["distance"] = float(distances[0][index])
        retrieved_chunks.append(metadata)

    return retrieved_chunks
