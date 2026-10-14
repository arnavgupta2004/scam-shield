"""
score_urgency.py — compute a weighted urgency score from text + entity flags.

Uses the signal table from kb/scam_playbooks.md:
  High (weight 3): arrest/police/CBI/ED, secrecy, OTP/PIN/CVV/card/Aadhaar,
                   remote-access app / APK, UPI PIN request
  Medium (weight 2): deadline (today/tonight/hours), suspicious link/domain,
                     personal mobile for "official", guaranteed returns/prizes,
                     new number claiming to be family
  Low (weight 1): generic greeting ("Dear customer")

Score is the raw weighted sum normalised to 0–10 (capped at max possible = 30).
Level: high ≥ 6, medium ≥ 3, low < 3.

Signals are matched in English, Hindi (Devanagari) and Kannada.
"""

from __future__ import annotations

import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Signal definitions: (label, weight, compiled_pattern)
# ---------------------------------------------------------------------------

_SIGNALS: list[tuple[str, int, re.Pattern]] = [
    # ---- HIGH (3) -----------------------------------------------------------
    ("arrest/police/CBI/ED claim", 3, re.compile(
        r"\b(?:arrest|CBI|ED\b|Enforcement\s+Directorate|cyber\s*crime\s*police"
        r"|digital\s+arrest|custody|warrant)\b"
        r"|गिरफ्तार|डिजिटल\s*अरेस्ट|पुलिस"
        r"|ಗಿರಫ್ತಾರ|ಸೈಬರ್\s*ಕ್ರೈಮ್\s*ಪೊಲೀಸ್|ಪೊಲೀಸ್",
        re.IGNORECASE,
    )),
    ("secrecy instruction", 3, re.compile(
        r"don.?t\s+(?:tell|inform|share|let)\s+(?:anyone|family|papa|mom|anyone)"
        r"|stay\s+on\s+(?:call|video)"
        r"|do\s+not\s+inform\s+anyone"
        r"|किसी\s*को\s*मत\s*बताइए"
        r"|ಯಾರಿಗೂ\s*ಹೇಳಬೇಡಿ"
        r"|ಅಮ್ಮನಿಗೆ\s*ಹೇಳಬೇಡಿ",
        re.IGNORECASE,
    )),
    ("OTP/PIN/CVV/card request", 3, re.compile(
        r"\b(?:OTP|one.time.(?:password|code)|UPI\s*PIN|CVV|CVC|card\s*number"
        r"|enter\s+(?:your\s+)?PIN)\b"
        r"|ಓಟಿಪಿ",
        re.IGNORECASE,
    )),
    ("remote-access app or APK", 3, re.compile(
        r"\b(?:AnyDesk|TeamViewer|QuickSupport|ScreenConnect)\b"
        r"|\.apk\b",
        re.IGNORECASE,
    )),
    ("Aadhaar/PAN request", 3, re.compile(
        r"\b(?:Aadhaar|aadhaar\s*number|PAN\s*(?:card|number)?)\b"
        r"|ಆಧಾರ್",
        re.IGNORECASE,
    )),

    # ---- MEDIUM (2) ---------------------------------------------------------
    ("deadline — today/tonight/hours", 2, re.compile(
        r"\b(?:today|tonight|within\s+\d+\s+hours?|immediately|right\s+now"
        r"|urgent(?:ly)?|expires?\s+today)\b"
        r"|ತಕ್ಷಣ|ಇಂದು\s*ರಾತ್ರಿ|ವಿದ್ಯುತ್\s*ಕಡಿತ|अभी",
        re.IGNORECASE,
    )),
    ("suspicious link/domain/APK download", 2, re.compile(
        r"(?:bit\.ly|tinyurl|\.top/|\.xyz/|\.online|\.shop)"
        r"|download\s+\w+\.apk",
        re.IGNORECASE,
    )),
    ("personal mobile number for official", 2, re.compile(
        r"(?:officer|executive|helpline|contact)[\s\S]{0,30}[6-9]\d{9}",
        re.IGNORECASE,
    )),
    ("guaranteed returns / prize claim", 2, re.compile(
        r"\b(?:guaranteed\s+\d+%|guaranteed\s+return|300%|500%"
        r"|won\s+(?:Rs|₹)|lucky\s+draw|prize\s+money)\b"
        r"|लॉटरी\s+जीती|बधाई\s+हो",
        re.IGNORECASE,
    )),
    ("new number claiming to be family", 2, re.compile(
        r"new\s+number"
        r"|ಹೊಸ\s*ನಂಬರ್",
        re.IGNORECASE,
    )),
    ("money transfer demand", 2, re.compile(
        r"\b(?:transfer|send|pay|deposit|return)\s+(?:Rs\.?|₹)?\s*[\d,]+\b"
        r"|ವರ್ಗಾಯಿಸಿ|ಕಳಿಸಿ|वापस\s*भेज",
        re.IGNORECASE,
    )),

    # ---- LOW (1) ------------------------------------------------------------
    ("generic greeting", 1, re.compile(
        r"\bDear\s+(?:customer|consumer|user|sir|ma.?am)\b"
        r"|ಆತ್ಮೀಯ\s+ಗ್ರಾಹಕರೇ",
        re.IGNORECASE,
    )),
]

_MAX_RAW_SCORE: float = sum(w for _, w, _ in _SIGNALS)


def _raw_score(text: str, entities: dict) -> tuple[float, list[str]]:
    fired: list[str] = []
    total = 0.0
    for label, weight, pat in _SIGNALS:
        if pat.search(text):
            fired.append(label)
            total += weight
    # Bonus from entity flags (already counted in text scan, but APK/remote-app
    # may come from filename detection in extract_entities, not text keywords)
    if entities.get("has_apk") and "remote-access app or APK" not in fired:
        fired.append("remote-access app or APK (flag)")
        total += 3
    if entities.get("has_remote_app") and "remote-access app or APK" not in fired:
        fired.append("remote-access app or APK (flag)")
        total += 3
    return total, fired


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def _score_urgency_impl(text: str, entities: dict) -> dict:
    raw, fired = _raw_score(text, entities)
    normalised = round(min(raw / _MAX_RAW_SCORE * 10, 10.0), 2)
    # Thresholds: 3 high-weight signals → high (≥3.0); 1 medium signal → medium (≥1.0)
    if normalised >= 3.0:
        level = "high"
    elif normalised >= 1.0:
        level = "medium"
    else:
        level = "low"
    return {"score": normalised, "level": level, "signals": fired}


@tool
def score_urgency(text: str, entities: dict) -> dict:
    """
    Compute a weighted urgency score for *text* using red-flag signals from
    the scam playbooks, with multilingual (English / Hindi / Kannada) patterns.

    Args:
        text:     The (redacted) message text.
        entities: Output dict from extract_entities (boolean flags used).

    Returns:
        score   float  — 0–10 normalised score
        level   str    — "high" (≥6), "medium" (≥3), "low" (<3)
        signals list   — human-readable list of matched signals
    """
    return _score_urgency_impl(text, entities)
