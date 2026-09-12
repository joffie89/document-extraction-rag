"""Build a document, section, subsection, and paragraph hierarchy."""

import re

import tiktoken

from document_rag.infrastructure.chunking.semantic import semantic_units


def chunk_hierarchically(
    markdown: str,
    document_id: str,
    max_leaf_tokens: int,
) -> list[dict[str, object]]:
    """Create deterministic hierarchy nodes with bounded paragraph leaves."""

    if not document_id.strip():
        raise ValueError("A document identifier is required")
    if max_leaf_tokens < 1:
        raise ValueError("The leaf token limit must be positive")

    units = semantic_units(markdown)
    if not units:
        return []

    encoding = tiktoken.get_encoding("cl100k_base")
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    nodes: list[dict[str, object]] = [
        {
            "id": f"{document_id}:0",
            "parent_id": None,
            "kind": "document",
            "level": 0,
            "title": "Document",
            "text": "",
            "token_count": 0,
            "heading_path": "",
            "ancestor_ids": [],
        },
    ]
    root_node = nodes[0]
    section_stack: dict[int, dict[str, object]] = {}
    current_parent = root_node

    for unit in units:
        first_line = unit.splitlines()[0]
        heading_match = heading_pattern.match(first_line)

        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_title = heading_match.group(2).strip()

            for level in list(section_stack):
                if level >= heading_level:
                    section_stack.pop(level)

            parent_levels = []
            for candidate_level in section_stack:
                if candidate_level < heading_level:
                    parent_levels.append(candidate_level)
            parent_node = (
                section_stack[max(parent_levels)] if parent_levels else root_node
            )
            parent_heading_path = str(parent_node["heading_path"])
            heading_path = heading_title
            if parent_heading_path:
                heading_path = f"{parent_heading_path} > {heading_title}"

            section_node = {
                "id": f"{document_id}:{len(nodes)}",
                "parent_id": parent_node["id"],
                "kind": "section",
                "level": heading_level,
                "title": heading_title,
                "text": first_line,
                "token_count": len(encoding.encode(first_line)),
                "heading_path": heading_path,
                "ancestor_ids": [
                    *list(parent_node["ancestor_ids"]),
                    parent_node["id"],
                ],
            }
            nodes.append(section_node)
            section_stack[heading_level] = section_node
            current_parent = section_node
            continue

        encoded_unit = encoding.encode(unit)
        leaf_texts = []

        if len(encoded_unit) <= max_leaf_tokens:
            leaf_texts.append(unit)
        else:
            for start in range(0, len(encoded_unit), max_leaf_tokens):
                token_slice = encoded_unit[start : start + max_leaf_tokens]
                leaf_texts.append(encoding.decode(token_slice).strip())

        for leaf_text in leaf_texts:
            if not leaf_text:
                continue

            nodes.append(
                {
                    "id": f"{document_id}:{len(nodes)}",
                    "parent_id": current_parent["id"],
                    "kind": "paragraph",
                    "level": int(current_parent["level"]) + 1,
                    "title": "",
                    "text": leaf_text,
                    "token_count": len(encoding.encode(leaf_text)),
                    "heading_path": current_parent["heading_path"],
                    "ancestor_ids": [
                        *list(current_parent["ancestor_ids"]),
                        current_parent["id"],
                    ],
                },
            )

    leaf_nodes = [node for node in nodes if node["kind"] == "paragraph"]

    for node in nodes:
        if node["kind"] == "paragraph":
            continue

        descendant_texts = [
            str(leaf["text"])
            for leaf in leaf_nodes
            if node["id"] in leaf["ancestor_ids"]
        ]
        context_parts = []
        if node["kind"] == "section":
            context_parts.append(str(node["text"]))
        context_parts.extend(descendant_texts)
        node["text"] = "\n\n".join(context_parts)
        node["token_count"] = len(encoding.encode(str(node["text"])))

    nodes_by_id = {str(node["id"]): node for node in nodes}
    for leaf in leaf_nodes:
        parent_id = str(leaf["parent_id"])
        leaf["parent_text"] = nodes_by_id[parent_id]["text"]

    return nodes
