"""The test run must refuse outbound sockets."""

import socket

import pytest
import pytest_socket


def test_create_connection_is_blocked() -> None:
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.create_connection(("127.0.0.1", 9))
