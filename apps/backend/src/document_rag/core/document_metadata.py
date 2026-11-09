"""Derive document search labels from generic file and Markdown metadata."""

import re
from pathlib import Path

_ATX_HEADING = re.compile(r"^ {0,3}(?P<marks>#{1,6})\s+(?P<text>.+?)\s*$")
_CLOSING_MARKS = re.compile(r"\s+#+\s*$")
_LINK = re.compile(r"!?\[([^\]]+)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_INLINE_MARKUP = str.maketrans("", "", "*_~`")
_EXPLICIT_ABBREVIATION = re.compile(
    r"(?<!\w)\((?P<abbreviation>[A-Z][A-Z0-9&./-]{1,14})\)",
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_SHORT_NAME_SEPARATOR = re.compile(r"\s*(?::|\||\s[\u2013\u2014]\s)\s*")
_TRAILING_RELEASE_LABELS = (
    re.compile(
        r"(?:\s+|\s*[-\u2013\u2014|,:]\s*)"
        r"(?:\(?\s*)?"
        r"(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s+(?:19|20)\d{2}"
        r"(?:\s*\))?\s*$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:\s+|\s*[-\u2013\u2014|,:]\s*)"
        r"(?:\(?\s*)?"
        r"(?:19|20)\d{2}"
        r"(?:\s*[-\u2013\u2014/]\s*(?:(?:19|20)?\d{2}))?"
        r"(?:\s*\))?\s*$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:\s+|\s*[-\u2013\u2014|,:]\s*)"
        r"(?:\(?\s*)?"
        r"(?:v(?:ersion)?|ver(?:sion)?|rev(?:ision)?|edition)\s*"
        r"\d+(?:\.\d+)*"
        r"(?:\s*\))?\s*$",
        flags=re.IGNORECASE,
    ),
)
_ALIAS_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    },
)


def extract_document_metadata(
    source_file: str,
    markdown: str,
) -> dict[str, str]:
    """Return a title and aliases derived without corpus-specific knowledge.

    The aliases are newline-delimited because vector-store metadata values must
    remain scalar. Consumers can recover individual aliases with ``splitlines``.
    """

    filename_title = _filename_title(source_file)
    markdown_title = _first_markdown_heading(markdown)
    title = markdown_title or filename_title or source_file.strip()

    aliases: list[str] = []
    seen: set[str] = set()

    def add_alias(value: str) -> None:
        alias = " ".join(value.split()).strip()
        normalized = alias.casefold()
        if alias and normalized not in seen:
            aliases.append(alias)
            seen.add(normalized)

    labels = list(
        dict.fromkeys(
            (
                title,
                _short_name(title),
                _without_trailing_release_label(title),
                filename_title,
                _without_trailing_release_label(filename_title),
            )
        )
    )
    for label in labels:
        add_alias(label)

    for label in labels:
        for match in _EXPLICIT_ABBREVIATION.finditer(label):
            add_alias(match.group("abbreviation"))
        for initialism in _initialisms(label):
            add_alias(initialism)

    return {
        "document_title": title,
        "document_aliases": "\n".join(aliases),
    }


def _filename_title(source_file: str) -> str:
    """Turn a filename stem into a readable title without guessing its casing."""

    filename = source_file.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    stem = Path(filename).stem
    return " ".join(re.sub(r"[_-]+", " ", stem).split())


def _first_markdown_heading(markdown: str) -> str:
    """Prefer the first H1, falling back to the first ATX heading of any level."""

    headings: list[tuple[int, str]] = []
    fence: str | None = None
    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue

        match = _ATX_HEADING.match(line)
        if match is None:
            continue
        heading = _clean_heading(match.group("text"))
        if not heading:
            continue
        level = len(match.group("marks"))
        if level == 1:
            return heading
        headings.append((level, heading))

    return headings[0][1] if headings else ""


def _clean_heading(value: str) -> str:
    """Remove common inline Markdown decoration from a heading label."""

    value = _CLOSING_MARKS.sub("", value)
    value = _LINK.sub(r"\1", value)
    value = _HTML_TAG.sub("", value)
    value = value.translate(_INLINE_MARKUP)
    return " ".join(value.split())


def _short_name(title: str) -> str:
    """Use the leading title segment as a generic short-name candidate."""

    return _SHORT_NAME_SEPARATOR.split(title, maxsplit=1)[0]


def _without_trailing_release_label(label: str) -> str:
    """Remove generic trailing date, year-range, or version labels."""

    stripped = label.strip()
    changed = True
    while stripped and changed:
        changed = False
        for pattern in _TRAILING_RELEASE_LABELS:
            shortened = pattern.sub("", stripped).rstrip()
            if shortened != stripped:
                stripped = shortened
                changed = True
                break
    return stripped


def _initialisms(label: str) -> list[str]:
    """Build full and useful leading initialisms from significant words."""

    label = _EXPLICIT_ABBREVIATION.sub("", _short_name(label))
    words = [
        word
        for word in _WORD.findall(label)
        if word.casefold() not in _ALIAS_STOP_WORDS
    ]
    if not 2 <= len(words) <= 10:
        return []

    full_initialism = "".join(word[0].upper() for word in words)
    initialisms = [full_initialism]
    # Leading three-to-five-word forms capture commonly used short acronyms
    # without manufacturing every possible (and collision-prone) prefix.
    for length in range(3, min(5, len(words) - 1) + 1):
        initialisms.append("".join(word[0].upper() for word in words[:length]))
    return list(dict.fromkeys(initialisms))
