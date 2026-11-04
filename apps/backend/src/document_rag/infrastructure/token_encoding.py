"""Provide token encoding with a deterministic offline fallback."""

import logging
import re
from os import environ
from typing import Protocol

import tiktoken

logger = logging.getLogger(__name__)

OFFLINE_ENVIRONMENT_VARIABLE = "DOCUMENT_RAG_OFFLINE"
_TRUE_VALUES = {"1", "on", "true", "yes"}
_MAX_FALLBACK_TOKEN_BYTES = 8


class TokenEncoding(Protocol):
    """Describe the encoding operations used by the chunkers."""

    def encode(self, text: str) -> list[int]:
        """Convert text to token identifiers."""

    def decode(self, tokens: list[int]) -> str:
        """Convert token identifiers back to text."""


class LexicalTokenEncoding:
    """Use reversible lexical tokens when the BPE data is unavailable."""

    def encode(self, text: str) -> list[int]:
        """Represent bounded, whitespace-preserving pieces as integer tokens."""

        token_ids = []
        for lexical_piece in re.findall(r"\S+\s*|\s+", text):
            piece = ""
            piece_size = 0
            for character in lexical_piece:
                character_size = len(character.encode("utf-8"))
                if piece and piece_size + character_size > _MAX_FALLBACK_TOKEN_BYTES:
                    token_ids.append(self._encode_piece(piece))
                    piece = ""
                    piece_size = 0
                piece += character
                piece_size += character_size
            if piece:
                token_ids.append(self._encode_piece(piece))
        return token_ids

    def decode(self, tokens: list[int]) -> str:
        """Reconstruct text from self-contained integer tokens."""

        pieces = []
        for token in tokens:
            byte_count = max(1, (token.bit_length() + 7) // 8)
            encoded_piece = token.to_bytes(byte_count, "big")
            if not encoded_piece.startswith(b"\x01"):
                raise ValueError("Invalid offline token")
            pieces.append(encoded_piece[1:].decode("utf-8"))
        return "".join(pieces)

    @staticmethod
    def _encode_piece(piece: str) -> int:
        """Pack one short UTF-8 piece into a deterministic integer."""

        return int.from_bytes(b"\x01" + piece.encode("utf-8"), "big")


OFFLINE_ENCODING = LexicalTokenEncoding()


def get_token_encoding() -> TokenEncoding:
    """Prefer cl100k_base and fall back when its data cannot be downloaded."""

    offline_value = environ.get(OFFLINE_ENVIRONMENT_VARIABLE, "").casefold()
    if offline_value in _TRUE_VALUES:
        return OFFLINE_ENCODING

    try:
        return tiktoken.get_encoding("cl100k_base")
    except OSError:
        logger.warning(
            "cl100k_base is unavailable; using approximate offline tokenization, "
            "so chunk sizes may differ from production tiktoken chunk sizes",
        )
        return OFFLINE_ENCODING
