"""
Scam Shield API.

  POST /analyse  check a message or a live call (cues) -> verdict
  POST /alert    draft a family alert (only with user_confirmed = true)
  POST /report   simple reporting steps (1930, cybercrime.gov.in, Chakshu)
  GET  /health   configuration status

Run from the repo root:  uvicorn backend.main:app --reload
The frontend in frontend/ is served at http://localhost:8000/
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import fallback
from backend.orchestrate_client import OrchestrateClient, OrchestrateError
from backend.pipeline import prepare
from backend.verdict import extract_json, normalise_verdict

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

log = logging.getLogger("scam_shield")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

Lang = Literal["en", "hi", "kn"]


def _agent_ids() -> dict[str, str]:
    triage = os.environ.get("TRIAGE_AGENT_ID", "")
    return {
        "analyse": os.environ.get("ANALYSE_AGENT_ID") or triage,
        "guardian": os.environ.get("GUARDIAN_AGENT_ID", ""),
        "report": os.environ.get("REPORT_AGENT_ID", ""),
    }


app = FastAPI(title="Scam Shield", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_client(request: Request) -> OrchestrateClient | None:
    """Return the shared Orchestrate client, or None if not configured."""
    client = getattr(request.app.state, "client", None)
    if client is not None:
        return client
    try:
        client = OrchestrateClient.from_env()
    except OrchestrateError:
        return None
    request.app.state.client = client
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MD_BOLD = re.compile(r"\*{1,2}(.*?)\*{1,2}")         # **text** or *text*
_MD_ITALIC = re.compile(r"_(.*?)_")                    # _text_
_BRACKET_NOTE = re.compile(r"\[[^\]]{0,120}\]")        # [Note: ...] / [bracketed]
_LEADING_DASH = re.compile(r"(?m)^[-•]\s+")            # bullet dashes


def _clean_report(text: str) -> str:
    """Strip markdown and meta-notes from a report_helper agent reply."""
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_ITALIC.sub(r"\1", text)
    text = _BRACKET_NOTE.sub("", text)
    text = _LEADING_DASH.sub("", text)
    # Collapse multiple spaces left by removals, and trim each line
    lines = [" ".join(l.split()) for l in text.splitlines()]
    # Drop blank lines produced by removing bracketed notes that were on their own line
    lines = [l for l in lines if l.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    text: str = Field("", max_length=4000)
    lang: Lang = "en"
    mode: Literal["message", "live_coach"] = "message"
    cues: list[str] = Field(default_factory=list, max_length=10)


class AnalyseResponse(BaseModel):
    verdict: Literal["scam", "genuine", "uncertain"]
    scam_type: str | None
    confidence: Literal["high", "medium", "low"]
    red_flags: list[str]
    explanation: str
    advice: str
    source: Literal["agent", "rules"]
    latency_ms: int
    redacted_text: str


class AlertRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=600)
    lang: Lang = "en"
    user_confirmed: bool = False


class ReportRequest(BaseModel):
    lang: Lang = "en"
    scam_type: str | None = Field(None, max_length=60)
    summary: str = Field("", max_length=600)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(request: Request):
    ids = _agent_ids()
    return {
        "status": "ok",
        "orchestrate_configured": get_client(request) is not None,
        "agents_configured": {k: bool(v) for k, v in ids.items()},
    }


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse(req: AnalyseRequest, request: Request):
    if not req.text.strip() and not req.cues:
        raise HTTPException(status_code=422, detail="Provide text or at least one cue.")

    started = time.perf_counter()
    prepared = prepare(req.text, req.lang, req.mode, req.cues)
    client = get_client(request)
    agent_id = _agent_ids()["analyse"]

    result = None
    if client and agent_id:
        try:
            reply = await client.chat(agent_id, json.dumps(prepared["payload"], ensure_ascii=False))
            result = normalise_verdict(extract_json(reply, "verdict"))
            if result is None:
                log.warning("analyse: agent reply had no usable verdict JSON")
        except OrchestrateError as exc:
            log.warning("analyse: orchestrate unavailable (%s)", exc)
        except Exception as exc:  # network errors, timeouts
            log.warning("analyse: orchestrate call failed (%s)", type(exc).__name__)

    source = "agent"
    if result is None:
        source = "rules"
        result = fallback.rules_verdict(prepared["urgency"], prepared["pattern"], req.lang,
                                        prepared["payload"]["cues"])

    latency_ms = int((time.perf_counter() - started) * 1000)
    # Log only outcome metadata, never message content.
    log.info("analyse lang=%s mode=%s verdict=%s source=%s latency_ms=%d",
             req.lang, req.mode, result["verdict"], source, latency_ms)
    return {**result, "source": source, "latency_ms": latency_ms,
            "redacted_text": prepared["redacted_text"]}


@app.post("/alert")
async def alert(req: AlertRequest, request: Request):
    # Human-in-the-loop gate: nothing is drafted without explicit confirmation.
    if req.user_confirmed is not True:
        raise HTTPException(status_code=403, detail={"status": "needs_confirmation"})

    summary = prepare(req.summary, req.lang)["redacted_text"]
    client = get_client(request)
    agent_id = _agent_ids()["guardian"]
    if client and agent_id:
        content = json.dumps({"summary": summary, "lang": req.lang, "user_confirmed": True}, ensure_ascii=False)
        try:
            reply = await client.chat(agent_id, content)
            obj = extract_json(reply, "message")
            if obj and obj.get("message"):
                return {"status": "drafted", "message": str(obj["message"]), "source": "agent"}
        except Exception as exc:
            log.warning("alert: guardian call failed (%s)", type(exc).__name__)
    return {"status": "drafted", "message": fallback.alert_message(summary, req.lang), "source": "template"}


@app.post("/report")
async def report(req: ReportRequest, request: Request):
    summary = prepare(req.summary, req.lang)["redacted_text"] if req.summary else ""
    client = get_client(request)
    agent_id = _agent_ids()["report"]
    if client and agent_id:
        content = json.dumps({"lang": req.lang, "scam_type": req.scam_type, "summary": summary}, ensure_ascii=False)
        try:
            reply = (await client.chat(agent_id, content)).strip()
            if reply:
                return {"steps": _clean_report(reply), "source": "agent"}
        except Exception as exc:
            log.warning("report: report_helper call failed (%s)", type(exc).__name__)
    return {"steps": fallback.report_steps(req.lang), "source": "template"}


# Serve the frontend last so API routes take precedence.
_FRONTEND = REPO_ROOT / "frontend"
if _FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
