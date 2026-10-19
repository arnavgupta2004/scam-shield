"""
Pytest fixtures for Playwright e2e tests.

The backend is started in a background thread with Orchestrate mocked by an
httpx.MockTransport, so no real credentials or network calls are needed.
The FakeOrchestrate helper mirrors the one in backend/test_backend.py.
"""

from __future__ import annotations

import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from backend import main
from backend.orchestrate_client import OrchestrateClient

# ---------------------------------------------------------------------------
# Scripted Orchestrate reply — a clear scam verdict used by all tests.
# ---------------------------------------------------------------------------

SCAM_REPLY = json.dumps({
    "verdict": "scam",
    "scam_type": "digital_arrest",
    "confidence": "high",
    "red_flags": ["claims to be police", "demands secrecy"],
    "explanation": "Police never arrest people over video calls.",
    "advice": "Hang up now.",
})


def _sse(text: str) -> str:
    parts = [text[i:i + 20] for i in range(0, len(text), 20)]
    lines = [
        f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}"
        for p in parts
    ]
    return "\n\n".join(lines + ["data: [DONE]"]) + "\n\n"


class FakeOrchestrate:
    """Mock httpx transport: token endpoint returns a token; all others return
    a scripted SSE reply so no real Orchestrate credentials are needed."""

    def __init__(self, reply: str = SCAM_REPLY):
        self.reply = reply

    def handler(self, request: httpx.Request) -> httpx.Response:
        if "apikeys/token" in str(request.url):
            return httpx.Response(200, json={"token": "fake-tok", "expires_in": 3600})
        return httpx.Response(200, text=_sse(self.reply))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    """Start the FastAPI app once for the whole e2e session on a free port.

    app.state.client is pre-loaded with the FakeOrchestrate transport so
    every /analyse, /alert and /report call is answered without any real
    Orchestrate instance or credentials.
    """
    port = _free_port()
    fake = FakeOrchestrate()

    # Inject mock client and required agent-id env vars before the server loop
    # reads them.  These values only need to be non-empty strings.
    import os
    os.environ.setdefault("TRIAGE_AGENT_ID", "e2e-triage")
    os.environ.setdefault("GUARDIAN_AGENT_ID", "e2e-guardian")
    os.environ.setdefault("REPORT_AGENT_ID", "e2e-report")

    main.app.state.client = OrchestrateClient(
        "https://wo.example", "fake-key",
        transport=httpx.MockTransport(fake.handler),
    )

    config = uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is actually accepting connections.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("e2e live server did not start within 10 s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)
    main.app.state.client = None
