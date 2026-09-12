"""Detect semantic boundaries between Markdown blocks."""

import math
import re

import tiktoken
from markdown_it import MarkdownIt


def semantic_units(markdown: str) -> list[str]:
    """Split Markdown into intact structural blocks for embedding."""

    if not markdown.strip():
        return []

    source_lines = markdown.splitlines()
    parser = MarkdownIt("commonmark").enable("table")
    tokens = parser.parse(markdown)
    block_types = {
        "blockquote_open",
        "bullet_list_open",
        "code_block",
        "fence",
        "heading_open",
        "html_block",
        "hr",
        "ordered_list_open",
        "paragraph_open",
        "table_open",
    }
    units = []
    captured_until = 0

    for token in tokens:
        if token.type not in block_types or token.map is None:
            continue

        start_line, end_line = token.map
        if start_line < captured_until:
            continue

        block = "\n".join(source_lines[start_line:end_line]).strip()
        if block:
            units.append(block)
            captured_until = end_line

    return units


def chunk_semantically(
    units: list[str],
    embeddings: list[list[float]],
    break_percentile: int,
    min_tokens: int,
    max_tokens: int,
) -> list[dict[str, object]]:
    """Group embedded blocks at semantic and structural boundaries."""

    if len(units) != len(embeddings):
        raise ValueError("Each semantic unit requires one embedding")
    if not units:
        return []
    if not 1 <= break_percentile <= 99:
        raise ValueError("The semantic break percentile must be between 1 and 99")
    if min_tokens < 1 or min_tokens >= max_tokens:
        raise ValueError("Chunk token limits are invalid")

    embedding_size = len(embeddings[0])
    if embedding_size == 0:
        raise ValueError("Embeddings cannot be empty")

    distances = []
    for left_embedding, right_embedding in zip(
        embeddings,
        embeddings[1:],
        strict=False,
    ):
        if len(left_embedding) != embedding_size:
            raise ValueError("Embedding dimensions do not match")
        if len(right_embedding) != embedding_size:
            raise ValueError("Embedding dimensions do not match")

        dot_product = sum(
            left_value * right_value
            for left_value, right_value in zip(
                left_embedding,
                right_embedding,
                strict=True,
            )
        )
        left_norm = math.sqrt(sum(value * value for value in left_embedding))
        right_norm = math.sqrt(sum(value * value for value in right_embedding))
        if left_norm == 0 or right_norm == 0:
            raise ValueError("Embeddings cannot contain zero-length vectors")

        similarity = dot_product / (left_norm * right_norm)
        distances.append(1 - max(-1.0, min(1.0, similarity)))

    if len(embeddings[-1]) != embedding_size:
        raise ValueError("Embedding dimensions do not match")

    sorted_distances = sorted(distances)
    if sorted_distances:
        percentile_position = (len(sorted_distances) - 1) * break_percentile / 100
        lower_index = math.floor(percentile_position)
        upper_index = math.ceil(percentile_position)
        interpolation = percentile_position - lower_index
        distance_threshold = sorted_distances[lower_index] + interpolation * (
            sorted_distances[upper_index] - sorted_distances[lower_index]
        )
    else:
        distance_threshold = math.inf

    encoding = tiktoken.get_encoding("cl100k_base")
    unit_token_counts = [len(encoding.encode(unit)) for unit in units]
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    heading_stack: dict[int, str] = {}
    chunks: list[dict[str, object]] = []
    current_units: list[str] = []
    current_tokens = 0
    current_heading_path = ""

    for index, unit in enumerate(units):
        unit_tokens = unit_token_counts[index]

        if current_units and current_tokens + unit_tokens > max_tokens:
            chunks.append(
                {
                    "text": "\n\n".join(current_units),
                    "ordinal": len(chunks),
                    "token_count": current_tokens,
                    "kind": "semantic",
                    "level": 0,
                    "parent_id": None,
                    "heading_path": current_heading_path,
                },
            )
            current_units = []
            current_tokens = 0

        heading_match = heading_pattern.match(unit.splitlines()[0])
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_stack[heading_level] = heading_match.group(2).strip()
            heading_stack = {
                level: title
                for level, title in heading_stack.items()
                if level <= heading_level
            }

        if not current_units:
            current_heading_path = " > ".join(
                heading_stack[level] for level in sorted(heading_stack)
            )

        current_units.append(unit)
        current_tokens += unit_tokens
        next_unit_is_heading = index + 1 < len(units) and bool(
            heading_pattern.match(units[index + 1].splitlines()[0]),
        )
        semantic_boundary = (
            index < len(distances) and distances[index] > distance_threshold
        )
        should_finish = current_tokens >= min_tokens and (
            next_unit_is_heading or semantic_boundary
        )

        if should_finish:
            chunks.append(
                {
                    "text": "\n\n".join(current_units),
                    "ordinal": len(chunks),
                    "token_count": current_tokens,
                    "kind": "semantic",
                    "level": 0,
                    "parent_id": None,
                    "heading_path": current_heading_path,
                },
            )
            current_units = []
            current_tokens = 0

    if current_units:
        chunks.append(
            {
                "text": "\n\n".join(current_units),
                "ordinal": len(chunks),
                "token_count": current_tokens,
                "kind": "semantic",
                "level": 0,
                "parent_id": None,
                "heading_path": current_heading_path,
            },
        )

    return chunks
