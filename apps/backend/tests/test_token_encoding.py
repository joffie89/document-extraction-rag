"""Tests for online and offline token encoding selection."""

import logging
from unittest.mock import MagicMock

import pytest

import document_rag.infrastructure.token_encoding as token_encoding


def test_token_encoding_prefers_cl100k_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal runtime path should retain tiktoken's production encoding."""

    expected_encoding = MagicMock()
    get_encoding = MagicMock(return_value=expected_encoding)
    monkeypatch.delenv(token_encoding.OFFLINE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(token_encoding.tiktoken, "get_encoding", get_encoding)

    encoding = token_encoding.get_token_encoding()

    assert encoding is expected_encoding
    get_encoding.assert_called_once_with("cl100k_base")


def test_token_encoding_warns_when_tiktoken_falls_back_automatically(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An automatic fallback must clearly disclose different chunk sizing."""

    monkeypatch.delenv(token_encoding.OFFLINE_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(
        token_encoding.tiktoken,
        "get_encoding",
        MagicMock(side_effect=OSError("offline")),
    )

    with caplog.at_level(logging.WARNING, logger=token_encoding.__name__):
        encoding = token_encoding.get_token_encoding()
    text = "Safety glasses — 保護眼鏡"
    tokens = encoding.encode(text)

    assert encoding is token_encoding.OFFLINE_ENCODING
    assert "chunk sizes may differ" in caplog.text
    assert tokens == encoding.encode(text)
    assert encoding.decode(tokens) == text
    assert len(encoding.encode("x" * 100)) > 1


def test_explicit_offline_mode_does_not_call_tiktoken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests and offline runs should bypass the download path completely."""

    get_encoding = MagicMock(side_effect=AssertionError("unexpected download"))
    monkeypatch.setenv(token_encoding.OFFLINE_ENVIRONMENT_VARIABLE, "true")
    monkeypatch.setattr(token_encoding.tiktoken, "get_encoding", get_encoding)

    encoding = token_encoding.get_token_encoding()

    assert encoding is token_encoding.OFFLINE_ENCODING
    get_encoding.assert_not_called()
