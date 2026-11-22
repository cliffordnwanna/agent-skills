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

# Make CLI help output identical on every machine. GitHub Actions (GITHUB_ACTIONS) and the
# colour-forcing variables make Typer/Rich emit ANSI codes even when output is captured, which
# splits option names such as "--budget-usd" across escape sequences and breaks substring
# assertions. Typer reads these at import time, so they are set before any test imports the CLI.
for key in ("GITHUB_ACTIONS", "FORCE_COLOR", "PY_COLORS", "CLICOLOR_FORCE"):
    os.environ.pop(key, None)
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"
# Existing tests read the exact JSON. Readable output has its own tests (test_output.py).
os.environ["RAGKIT_OUTPUT"] = "json"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection

    def is_loopback(address):
        return isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost")

    def reject():
        raise AssertionError("Tests must not make external network connections")

    def guarded_connect(self, address):
        if not is_loopback(address):
            reject()
        return original_connect(self, address)

    def guarded_connect_ex(self, address):
        if not is_loopback(address):
            reject()
        return original_connect_ex(self, address)

    def guarded_create(address, *args, **kwargs):
        if not is_loopback(address):
            reject()
        return original_create(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create)
