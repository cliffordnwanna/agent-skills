import os
import socket

import pytest

# Set before test module imports: no external telemetry or accidentally inherited provider key.
for key, value in {
    "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
    "DEEPEVAL_DISABLE_DOTENV": "1",
    "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1",
    "DEEPEVAL_AUTO_TRACE": "0",
    "OTEL_SDK_DISABLED": "true",
}.items():
    os.environ[key] = value
for key in ("OPENAI_API_KEY", "RAGKIT_OPENAI_API_KEY", "CONFIDENT_API_KEY"):
    os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Tests must not make network connections")

    original_pair = socket.socketpair
    original_connect = socket.socket.connect

    def local_socketpair(*args, **kwargs):
        # Windows implements asyncio's local wakeup socketpair using loopback TCP.
        # Allow only this trusted stdlib constructor, not arbitrary client connections.
        with monkeypatch.context() as local:
            local.setattr(socket.socket, "connect", original_connect)
            return original_pair(*args, **kwargs)

    monkeypatch.setattr(socket, "socketpair", local_socketpair)
    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "connect_ex", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
