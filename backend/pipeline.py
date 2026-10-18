"""
Local pre-processing that runs before anything leaves the machine.

Order matters:
  1. extract_entities on the RAW text (phone numbers / UPI IDs are evidence)
  2. redact_pii, so only redacted text is sent to watsonx Orchestrate
  3. rule-based hints (urgency score + pattern match) on the redacted text

Only the redacted text, boolean flags and hints are forwarded. Raw values
(phones, URLs, UPI IDs) stay in this process and are never logged.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from agents.tools.extract_entities import _extract_entities_impl as extract_entities  # noqa: E402
from agents.tools.match_scam_pattern import _match_scam_pattern_impl as match_scam_pattern  # noqa: E402
from agents.tools.redact_pii import redact_pii  # noqa: E402
from agents.tools.score_urgency import _score_urgency_impl as score_urgency  # noqa: E402

FLAG_KEYS = ("has_personal_mobile", "has_upi_id", "has_url", "has_apk", "has_remote_app")

# Live-call cues the user can tap. Keys are sent by the frontend; the English
# phrasing is what the agent sees (it replies in the user's language anyway).
LIVE_CUES = {
    "police": "Caller says they are police, CBI, customs or a court and talks about arrest or a case",
    "money": "Caller is asking me to pay or transfer money",
    "otp": "Caller is asking for an OTP, PIN, card or bank details",
    "secret": "Caller says do not tell anyone and stay on the call",
    "app": "Caller wants me to install an app or open a link",
    "relative": "Caller says they are a relative or friend in trouble on a new number",
    "prize": "Caller says I won a prize, refund or high returns",
    "threat": "Caller threatens to cut electricity, block my account or leak a video",
}


def build_text(text: str, mode: str, cues: list[str]) -> str:
    """Combine typed text with live-call cues into one description."""
    parts = []
    if mode == "live_coach" and cues:
        known = [LIVE_CUES[c] for c in cues if c in LIVE_CUES]
        if known:
            parts.append("I am on a phone call right now. " + ". ".join(known) + ".")
    if text.strip():
        parts.append(text.strip())
    return " ".join(parts)


def prepare(text: str, lang: str, mode: str = "message", cues: list[str] | None = None) -> dict:
    """Run the local pipeline and return the payload for Orchestrate plus hints."""
    cues = cues or []
    raw = build_text(text, mode, cues)

    entities = extract_entities(raw)
    redacted = redact_pii(raw)
    urgency = score_urgency(redacted, entities)
    pattern = match_scam_pattern(redacted)

    flags = {k: bool(entities.get(k)) for k in FLAG_KEYS}

    payload = {
        "text": redacted,
        "lang": lang,
        "mode": mode,
        "flags": flags,
        "cues": [c for c in cues if c in LIVE_CUES],
        "urgency": urgency,
        "scam_type_hint": pattern.get("scam_type"),
    }
    return {"payload": payload, "redacted_text": redacted, "urgency": urgency, "pattern": pattern}
