"""Expose the formats registered by the installed Docling version."""

from docling.datamodel.base_models import FormatToExtensions


def supported_formats() -> dict[str, tuple[str, ...]]:
    """Return Docling format names with normalized file extensions."""

    return {
        input_format.value: tuple(f".{extension.lower()}" for extension in extensions)
        for input_format, extensions in FormatToExtensions.items()
    }


def matching_formats(file_name: str) -> list[str]:
    """Match a file name while preserving ambiguous and compound formats."""

    normalized_name = file_name.lower()
    matches: list[tuple[str, int]] = []

    for format_name, extensions in supported_formats().items():
        for extension in extensions:
            if normalized_name.endswith(extension):
                matches.append((format_name, len(extension)))

    if not matches:
        return []

    longest_extension = max(length for _, length in matches)
    longest_matches = set()

    for format_name, extension_length in matches:
        if extension_length == longest_extension:
            longest_matches.add(format_name)

    return sorted(longest_matches)
