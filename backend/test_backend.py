"""Backend tests. Orchestrate is mocked; no network or credentials needed.

Run from the repo root:  python -m pytest backend -q
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.orchestrate_client import OrchestrateClient, parse_reply
from backend.verdict import extract_json, normalise_verdict

ROW1 = ("This is Inspector Rao from Mumbai Cyber Crime. Your Aadhaar is linked to a money "
        "laundering case. You are under digital arrest. Stay on video call and do not inform "
        "anyone or you will be jailed.")
ROW37 = "123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI"


def sse(text: str) -> str:
    """Encode a reply as the SSE stream Orchestrate returns, split into chunks."""
    parts = [text[i:i + 15] for i in range(0, len(text), 15)]
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': p}}]})}" for p in parts]
    return "\n\n".join(lines + ["data: [DONE]"]) + "\n\n"


class FakeOrchestrate:
    """Mock transport: records what was sent, replies with a scripted body."""

    def __init__(self, reply: str = "", status: int = 200, raise_exc: Exception | None = None):
        self.reply = reply
        self.status = status
        self.raise_exc = raise_exc
        self.sent: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if "apikeys/token" in str(request.url):
            return httpx.Response(200, json={"token": "t", "expires_in": 3600})
        if self.raise_exc:
            raise self.raise_exc
        self.sent.append(json.loads(request.content))
        return httpx.Response(self.status, text=sse(self.reply) if self.status == 200 else "err")


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setenv("TRIAGE_AGENT_ID", "triage-id")
    monkeypatch.setenv("GUARDIAN_AGENT_ID", "guardian-id")
    monkeypatch.setenv("REPORT_AGENT_ID", "report-id")

    def _make(fake: FakeOrchestrate | None):
        if fake is None:
            main.app.state.client = None
            monkeypatch.delenv("WO_INSTANCE", raising=False)
            monkeypatch.delenv("WO_API_KEY", raising=False)
        else:
            main.app.state.client = OrchestrateClient(
                "https://wo.example", "key", transport=httpx.MockTransport(fake.handler))
        return TestClient(main.app)

    yield _make
    main.app.state.client = None


AGENT_SCAM = json.dumps({
    "verdict": "scam", "scam_type": "digital_arrest", "confidence": "high",
    "red_flags": ["fake arrest", "secrecy"], "explanation": "Police never arrest on video calls.",
    "advice": "Hang up now."})


# ---- parsing ---------------------------------------------------------------

def test_parse_reply_joins_sse_chunks():
    assert parse_reply(sse("hello world, this is long")) == "hello world, this is long"


def test_parse_reply_plain_json_body():
    body = json.dumps({"choices": [{"message": {"content": "hi"}}]})
    assert parse_reply(body) == "hi"


def test_extract_json_from_code_fence_and_prose():
    text = "Here you go:\n```json\n" + AGENT_SCAM + "\n```\nStay safe."
    assert extract_json(text, "verdict")["verdict"] == "scam"


def test_extract_json_skips_other_objects():
    text = '{"tool": "x"} then ' + AGENT_SCAM
    assert extract_json(text, "verdict")["scam_type"] == "digital_arrest"


def test_normalise_rejects_bad_verdict():
    assert normalise_verdict({"verdict": "maybe"}) is None
    assert normalise_verdict(None) is None


def test_normalise_genuine_clears_scam_type_and_caps_flags():
    out = normalise_verdict({"verdict": "Genuine", "scam_type": "x", "confidence": "?",
                             "red_flags": ["a", "b", "c", "d"]})
    assert out["verdict"] == "genuine" and out["scam_type"] is None
    assert out["confidence"] == "medium" and len(out["red_flags"]) == 3


# ---- /analyse --------------------------------------------------------------

def test_analyse_uses_agent_and_sends_only_redacted_text(make_client):
    fake = FakeOrchestrate(reply=AGENT_SCAM)
    client = make_client(fake)
    text = ROW1 + " Call me on +91 98765 43210 and pay to rao@okaxis."
    r = client.post("/analyse", json={"text": text, "lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "scam" and body["source"] == "agent"

    sent = json.loads(fake.sent[0]["messages"][0]["content"])
    assert "98765" not in sent["text"] and "rao@okaxis" not in sent["text"]
    assert "[PHONE]" in sent["text"] and "[UPI]" in sent["text"]
    assert sent["flags"]["has_personal_mobile"] and sent["flags"]["has_upi_id"]
    assert sent["lang"] == "en"


def test_analyse_redacts_otp(make_client):
    fake = FakeOrchestrate(reply=json.dumps({"verdict": "genuine", "confidence": "high"}))
    client = make_client(fake)
    r = client.post("/analyse", json={"text": ROW37, "lang": "en"})
    assert r.json()["verdict"] == "genuine"
    assert "123456" not in fake.sent[0]["messages"][0]["content"]


def test_analyse_live_coach_cues_reach_agent(make_client):
    fake = FakeOrchestrate(reply=AGENT_SCAM)
    client = make_client(fake)
    r = client.post("/analyse", json={"text": "", "lang": "kn", "mode": "live_coach",
                                      "cues": ["police", "secret", "bogus"]})
    assert r.status_code == 200
    sent = json.loads(fake.sent[0]["messages"][0]["content"])
    assert sent["mode"] == "live_coach" and sent["cues"] == ["police", "secret"]
    assert "phone call right now" in sent["text"]


def test_analyse_falls_back_to_rules_when_agent_down(make_client):
    client = make_client(FakeOrchestrate(status=500))
    body = client.post("/analyse", json={"text": ROW1, "lang": "hi"}).json()
    assert body["source"] == "rules" and body["verdict"] == "scam"
    assert "धोखाधड़ी" in body["explanation"]


def test_analyse_falls_back_on_timeout(make_client):
    client = make_client(FakeOrchestrate(raise_exc=httpx.ReadTimeout("slow")))
    body = client.post("/analyse", json={"text": ROW1, "lang": "en"}).json()
    assert body["source"] == "rules"


def test_analyse_falls_back_on_unparseable_reply(make_client):
    client = make_client(FakeOrchestrate(reply="Sorry, I cannot help."))
    body = client.post("/analyse", json={"text": ROW37, "lang": "en"}).json()
    assert body["source"] == "rules"
    assert body["verdict"] == "uncertain"  # fallback never claims "genuine"


def test_live_coach_fallback_flags_danger_cues(make_client):
    client = make_client(FakeOrchestrate(status=503))
    body = client.post("/analyse", json={"lang": "en", "mode": "live_coach", "cues": ["police", "secret"]}).json()
    assert body["source"] == "rules" and body["verdict"] == "scam"
    body = client.post("/analyse", json={"lang": "en", "mode": "live_coach", "cues": ["relative"]}).json()
    assert body["verdict"] == "uncertain"


def test_analyse_without_orchestrate_config(make_client):
    client = make_client(None)
    body = client.post("/analyse", json={"text": ROW1, "lang": "kn"}).json()
    assert body["source"] == "rules"


def test_analyse_rejects_empty_and_bad_lang(make_client):
    client = make_client(FakeOrchestrate(reply=AGENT_SCAM))
    assert client.post("/analyse", json={"text": "  ", "lang": "en"}).status_code == 422
    assert client.post("/analyse", json={"text": "hi", "lang": "fr"}).status_code == 422


# ---- /alert ----------------------------------------------------------------

def test_alert_refuses_without_confirmation(make_client):
    fake = FakeOrchestrate(reply='{"status":"drafted","message":"x"}')
    client = make_client(fake)
    for body in ({"summary": "fake police call", "lang": "en"},
                 {"summary": "fake police call", "lang": "en", "user_confirmed": False}):
        assert client.post("/alert", json=body).status_code == 403
    assert fake.sent == []  # guardian never called


def test_alert_with_confirmation_uses_guardian_and_redacts(make_client):
    fake = FakeOrchestrate(reply='{"status":"drafted","message":"Please call me now."}')
    client = make_client(fake)
    r = client.post("/alert", json={"summary": "caller asked OTP 482913, number 9876543210",
                                    "lang": "en", "user_confirmed": True})
    assert r.status_code == 200 and r.json()["source"] == "agent"
    content = fake.sent[0]["messages"][0]["content"]
    assert "482913" not in content and "9876543210" not in content
    assert json.loads(content)["user_confirmed"] is True


def test_alert_template_fallback(make_client):
    client = make_client(FakeOrchestrate(status=502))
    r = client.post("/alert", json={"summary": "fake police call", "lang": "kn", "user_confirmed": True})
    assert r.json()["source"] == "template" and "ನಮಸ್ಕಾರ" in r.json()["message"]


# ---- /report and /health ---------------------------------------------------

def test_report_agent_and_fallback(make_client):
    client = make_client(FakeOrchestrate(reply="1. Call 1930"))
    assert client.post("/report", json={"lang": "en"}).json()["source"] == "agent"
    client = make_client(FakeOrchestrate(status=500))
    steps = client.post("/report", json={"lang": "en"}).json()
    assert steps["source"] == "template" and "1930" in steps["steps"]


def test_health(make_client):
    client = make_client(FakeOrchestrate(reply=""))
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["agents_configured"]["analyse"] is True
