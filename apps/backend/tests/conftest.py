"""Keep the backend test suite independent of credentials and networking."""

import socket
from ipaddress import ip_address
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def disable_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test without API credentials or outbound socket access."""

    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DOCUMENT_RAG_OFFLINE", "1")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def is_loopback(host: object) -> bool:
        if host is None or str(host).casefold() == "localhost":
            return True
        try:
            return ip_address(str(host)).is_loopback
        except ValueError:
            return False

    def guarded_connect(
        sock: socket.socket,
        address: tuple[Any, ...] | str,
    ) -> None:
        if isinstance(address, tuple) and is_loopback(address[0]):
            original_connect(sock, address)
            return
        raise AssertionError("External network access is disabled during tests")

    def guarded_connect_ex(
        sock: socket.socket,
        address: tuple[Any, ...] | str,
    ) -> int:
        if isinstance(address, tuple) and is_loopback(address[0]):
            return original_connect_ex(sock, address)
        raise AssertionError("External network access is disabled during tests")

    def guarded_create_connection(
        address: tuple[str, int],
        *args: object,
        **kwargs: object,
    ) -> socket.socket:
        if is_loopback(address[0]):
            return original_create_connection(address, *args, **kwargs)
        raise AssertionError("External network access is disabled during tests")

    def guarded_getaddrinfo(
        host: str | bytes | None,
        *args: object,
        **kwargs: object,
    ) -> list[tuple[Any, ...]]:
        if is_loopback(host):
            return original_getaddrinfo(host, *args, **kwargs)
        raise AssertionError("External network access is disabled during tests")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
